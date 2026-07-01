# -*- coding: utf-8 -*-
"""
QModelsClient — the one way the Sapphire orchestrator calls any Q-Models tool.

Routing is by the tool's `tier` in registry.json (two-speed):
  - local-cpu  → SYNCHRONOUS. POST the vendored Explorer backend /api/predict/{track}
                 (CPU joblibs; instant; $0). Provenance = live-local if the track is live,
                 else stub (the endpoint returned its documented stub_prediction).
  - gpu-launch | endpoint | batch-ec2 → ASYNCHRONOUS. Hand to the unified launcher
                 (auto-launch a tagged sapphire-qmodels instance → run the eval → retrieve →
                 auto-teardown). Returns a job handle; poll with .poll(job_id).
  - deprecated | todo → addressable but never called; returns an honest 'unavailable'.

R-SAPPHIRE SHORTCUT: when SAPPHIRE_QMODELS_GPU_ENDPOINT is set (pointing at the
persistent warm R-Sapphire box), BOTH local-cpu AND gpu-launch/endpoint/batch-ec2 tools
are routed through that single endpoint via POST /predict (the Explorer inference server
protocol). This keeps the laptop light (no model weights locally) and skips the async
launcher for GPU tools. Degrades honestly to the existing path when the env is unset or
the endpoint is unreachable (connection error → falls through to local/launcher).

Every return carries `provenance` so the dossier/Console never shows a fabricated number as real.
Stdlib only. The launcher is imported lazily so the client works before the launcher exists / when
GPU is disabled (QMODELS_GPU=off).
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

HERE = Path(__file__).resolve().parent
REGISTRY_PATH = HERE / "registry.json"
DEFAULT_LOCAL_URL = os.environ.get("QMODELS_LOCAL_URL", "http://127.0.0.1:8000")
GPU_ENABLED = os.environ.get("QMODELS_GPU", "on").lower() not in ("off", "0", "false")
# WO-9 Phase 4: gate REAL AWS launches behind SAPPHIRE_QMODELS_LIVE=1 (default OFF = dry-run).
# When OFF, GPU-tier tools return a clearly-labeled dry-run result (provenance=gpu-dry-run).
# When ON, the launcher is invoked for real (provenance=gpu-live on completion, gpu-stub on error).
QMODELS_LIVE = os.environ.get("SAPPHIRE_QMODELS_LIVE", "0").strip() in ("1", "true", "yes")

# WO-9: R-Sapphire persistent warm all-model endpoint.
# When set, BOTH local-cpu and gpu tools route here (POST /predict, Explorer inference protocol).
# Format: "http://<public-ip>:8080/predict"
# Unset/empty or endpoint unreachable → honest degradation to local/launcher paths.
_RSAPPHIRE_ENDPOINT_ENV = "SAPPHIRE_QMODELS_GPU_ENDPOINT"


def _rsapphire_endpoint() -> str | None:
    ep = os.environ.get(_RSAPPHIRE_ENDPOINT_ENV, "").strip()
    return ep if ep else None


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class QModelsClient:
    def __init__(self, local_url: str = DEFAULT_LOCAL_URL, registry: Optional[dict] = None, timeout: float = 20.0):
        self.local_url = local_url.rstrip("/")
        self.timeout = timeout
        self.registry = registry or load_registry()
        # id -> tool. tracks win over models on shared ids (tracks are the curated interface).
        self._tools: dict[str, dict] = {}
        for m in self.registry.get("models", []):
            self._tools[m["id"]] = m
        for t in self.registry.get("tracks", []):
            self._tools[t["id"]] = t

    # ---------- introspection ----------
    def tools(self) -> list[dict]:
        return list(self._tools.values())

    def get(self, tool_id: str) -> Optional[dict]:
        return self._tools.get(tool_id)

    def health(self) -> dict:
        """Is the local Explorer endpoint up, and which tracks are live-local?"""
        try:
            with urllib.request.urlopen(self.local_url + "/api/meta", timeout=5) as r:
                meta = json.loads(r.read())
            return {"reachable": True, "live_tracks": meta.get("live_tracks", []), "meta": meta}
        except Exception as e:
            return {"reachable": False, "live_tracks": [], "error": f"{type(e).__name__}: {e}"}

    def rsapphire_health(self) -> dict:
        """Is the R-Sapphire endpoint reachable? GET /health."""
        ep = _rsapphire_endpoint()
        if not ep:
            return {"reachable": False, "reason": "SAPPHIRE_QMODELS_GPU_ENDPOINT not set"}
        # /health is relative to the base URL (strip /predict suffix if present)
        base = ep.rstrip("/").removesuffix("/predict")
        try:
            with urllib.request.urlopen(base + "/health", timeout=8) as r:
                return {"reachable": True, "endpoint": ep, "health": json.loads(r.read())}
        except Exception as e:
            return {"reachable": False, "endpoint": ep, "error": f"{type(e).__name__}: {e}"}

    # ---------- R-Sapphire routing ----------
    def _call_rsapphire(self, tool: dict, inputs: dict, adapters) -> dict | None:
        """POST to R-Sapphire /predict. Returns normalized result or None on unreachable/error.

        Protocol: POST {"track": <id>, "model": <aws_model_key>, "inputs": <inputs>}
        — same as the Explorer inference.py live path. On connection failure → returns None
        (caller falls through to local/launcher). On HTTP error → returns an error dict
        (endpoint is up but rejected the request; do NOT fall through to avoid double-charging).
        """
        ep = _rsapphire_endpoint()
        if not ep:
            return None
        tool_id = tool.get("id", "")
        # aws_model_key from the tool; fall back to tool_id for local tracks (dti/bbbp/toxicity)
        model_key = tool.get("aws_model_key") or tool_id
        body = json.dumps({"track": tool_id, "model": model_key, "inputs": inputs}).encode("utf-8")
        req = urllib.request.Request(
            ep, data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                pred = json.loads(r.read())
        except urllib.error.HTTPError as e:
            # HTTPError must be caught BEFORE URLError (it is a subclass of URLError).
            # Endpoint is reachable but returned an error status → return error dict (no fall-through).
            detail = e.read().decode("utf-8", "replace")[:300] if hasattr(e, "read") else str(e)
            return {"ok": False, "tool_id": tool_id, "provenance": "rsapphire-error",
                    "note": f"R-Sapphire HTTP {e.code}: {detail}", "out": f"(rsapphire HTTP {e.code})"}
        except urllib.error.URLError:
            # Endpoint unreachable (DNS, refused, timeout) → fall through to local/launcher
            return None
        except Exception as e:
            return None  # unexpected error → fall through
        row = adapters.normalize(tool, pred, "rsapphire-live")
        row["ok"] = True
        row["provenance"] = "rsapphire-live"
        return row

    # ---------- the call ----------
    def call(self, tool_id: str, inputs: dict, *, live_tracks: Optional[list] = None) -> dict:
        from . import adapters
        tool = self.get(tool_id)
        if not tool:
            return {"ok": False, "tool_id": tool_id, "provenance": "unknown", "error": "unknown tool"}
        status = tool.get("status", "")
        tier = tool.get("tier", "")

        if status in ("deprecated", "todo"):
            return {"ok": False, "tool_id": tool_id, "provenance": "unavailable",
                    "model": tool.get("label") or tool.get("name"),
                    "note": f"{tool_id} is {status} — registered but not called.", "out": f"({status})"}

        # R-Sapphire shortcut: route ALL tiers through the warm endpoint when available.
        # Honest degradation: unreachable → falls through to the existing per-tier path.
        if _rsapphire_endpoint():
            result = self._call_rsapphire(tool, inputs, adapters)
            if result is not None:
                return result
            # Fall through: endpoint unreachable

        if tier == "local-cpu":
            return self._call_local(tool, inputs, live_tracks, adapters)
        if tier in ("gpu-launch", "endpoint", "batch-ec2"):
            return self._submit_gpu(tool, inputs)
        return {"ok": False, "tool_id": tool_id, "provenance": "unavailable",
                "note": f"unhandled tier '{tier}'", "out": "(unhandled)"}

    def _call_local(self, tool: dict, inputs: dict, live_tracks, adapters) -> dict:
        track = (tool.get("invoke") or {}).get("local_track") or tool["id"]
        if live_tracks is None:
            live_tracks = self.health().get("live_tracks", [])
        url = f"{self.local_url}/api/predict/{track}"
        try:
            req = urllib.request.Request(
                url, data=json.dumps(inputs).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.loads(r.read())
        except urllib.error.URLError as e:
            return {"ok": False, "tool_id": tool["id"], "provenance": "unavailable",
                    "model": tool.get("label"),
                    "note": f"local Explorer endpoint unreachable ({e}). Start it with serve_local.sh / setup_new_device.sh.",
                    "out": "(endpoint down)"}
        except Exception as e:
            return {"ok": False, "tool_id": tool["id"], "provenance": "error", "note": str(e), "out": "(error)"}
        # The Explorer wraps the prediction; accept either the body or body['prediction'].
        pred = body.get("prediction", body) if isinstance(body, dict) else body
        provenance = "live-local" if track in (live_tracks or []) else "stub"
        row = adapters.normalize(tool, pred, provenance)
        row["ok"] = True
        return row

    def _submit_gpu(self, tool: dict, inputs: dict) -> dict:
        """Route a GPU-tier tool call.

        Default (SAPPHIRE_QMODELS_LIVE not set): dry-run only — render the launch plan,
        record the tool_id/label/inputs, return provenance=gpu-dry-run. Zero AWS calls.

        Live opt-in (SAPPHIRE_QMODELS_LIVE=1): delegate to the launcher lifecycle —
        auto-launch a tagged Sapphire EC2, attach EBS, run *_eval.py, retrieve result.json,
        teardown by ledgered id. Provenance=gpu-live on success, gpu-stub on error.
        All AWS safety guards are in launcher.py (profile Rohan-Sapphire, account-gate,
        create-only ledger, teardown-only-by-ledgered-id, budget cap).
        """
        if not GPU_ENABLED:
            return {"ok": False, "tool_id": tool["id"], "provenance": "gpu-disabled",
                    "model": tool.get("label") or tool.get("name"),
                    "note": "GPU tools disabled (QMODELS_GPU=off). Set QMODELS_GPU=on to enable the launcher.",
                    "out": "(gpu disabled)"}
        try:
            from . import launcher  # lazy: only imported on a GPU call (may touch AWS in live mode)
        except Exception as e:
            return {"ok": False, "tool_id": tool["id"], "provenance": "gpu-stub",
                    "note": f"launcher unavailable: {e}", "out": "(launcher missing)"}

        tool_id = tool["id"]
        tool_label = tool.get("label") or tool.get("name") or tool_id

        if not QMODELS_LIVE:
            # DRY-RUN: render the launch plan + validate the recipe; no AWS call.
            # submit_job(mode="dry-run") is pure-local (validates userdata, writes a job file).
            job = launcher.submit_job(tool, inputs, mode="dry-run")
            return {
                "ok": True,
                "tool_id": tool_id,
                "provenance": "gpu-dry-run",
                "model": tool_label,
                "job_id": job.get("job_id"),
                "status": "dry-run",
                "note": (job.get("note") or
                         "Dry-run: set SAPPHIRE_QMODELS_LIVE=1 to launch a real Sapphire EC2, "
                         "or set SAPPHIRE_QMODELS_GPU_ENDPOINT to route through R-Sapphire."),
                "out": (f"GPU tool {tool_id!r} selected; would launch tagged Sapphire EC2 (dry-run). "
                        f"Label: {tool_label}. "
                        f"Input recorded. Set SAPPHIRE_QMODELS_LIVE=1 for a real run."),
            }

        # LIVE PATH (SAPPHIRE_QMODELS_LIVE=1): every safety guard enforced inside launcher.
        try:
            job = launcher.submit_job(tool, inputs, mode="live")
        except Exception as e:
            return {"ok": False, "tool_id": tool_id, "provenance": "gpu-stub",
                    "model": tool_label,
                    "note": f"launcher submit failed: {e}", "out": "(gpu launch failed)"}

        if job.get("status") in ("refused-budget", "dry-run-validated"):
            return {"ok": False, "tool_id": tool_id, "provenance": "gpu-stub",
                    "model": tool_label,
                    "note": job.get("note", "launch refused"), "out": "(launch refused)"}

        # Job launched — wait for completion + result retrieval.
        try:
            job = launcher.wait_for(job["job_id"])
        except Exception as e:
            return {"ok": False, "tool_id": tool_id, "provenance": "gpu-stub",
                    "model": tool_label,
                    "note": f"wait_for failed: {e}", "out": "(wait failed)"}

        if job.get("status") == "done" and job.get("result"):
            return {
                "ok": True,
                "tool_id": tool_id,
                "provenance": "gpu-live",
                "model": tool_label,
                "job_id": job.get("job_id"),
                "instance_id": job.get("instance_id"),
                "status": "done",
                "result": job["result"],
                "out": str(job["result"]),
            }
        # done-no-result / timeout-torn-down / other terminal states
        return {"ok": False, "tool_id": tool_id, "provenance": "gpu-stub",
                "model": tool_label,
                "job_id": job.get("job_id"),
                "note": job.get("note", f"job ended with status={job.get('status')}"),
                "out": "(gpu run ended without a retrievable result)"}

    def poll(self, job_id: str) -> dict:
        try:
            from . import launcher
        except Exception as e:
            return {"ok": False, "job_id": job_id, "status": "error", "note": str(e)}
        return launcher.job_status(job_id)


# convenience singleton
ENGINE_CLIENT = None
def client() -> "QModelsClient":
    global ENGINE_CLIENT
    if ENGINE_CLIENT is None:
        ENGINE_CLIENT = QModelsClient()
    return ENGINE_CLIENT
