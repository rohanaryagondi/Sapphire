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
                         "Dry-run: set SAPPHIRE_QMODELS_LIVE=1 to launch a real Sapphire EC2."),
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
