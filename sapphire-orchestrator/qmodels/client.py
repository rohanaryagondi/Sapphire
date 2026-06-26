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
        if not GPU_ENABLED:
            return {"ok": False, "tool_id": tool["id"], "provenance": "gpu-disabled",
                    "model": tool.get("label") or tool.get("name"),
                    "note": "GPU tools disabled (QMODELS_GPU=off). Set QMODELS_GPU=on to enable the launcher.",
                    "out": "(gpu disabled)"}
        try:
            from . import launcher  # lazy: launcher may run real AWS — only imported on a GPU call
        except Exception as e:
            return {"ok": False, "tool_id": tool["id"], "provenance": "gpu-async",
                    "note": f"launcher unavailable: {e}", "out": "(launcher missing)"}
        mode = os.environ.get("QMODELS_GPU_MODE", "dry-run")  # 'live' actually launches AWS; 'dry-run' renders the plan
        job = launcher.submit_job(tool, inputs, mode=mode)
        return {"ok": True, "tool_id": tool["id"], "provenance": ("gpu-live" if mode == "live" else "gpu-dry-run"),
                "model": tool.get("label") or tool.get("name"), "mode": mode,
                "job_id": job.get("job_id"), "status": job.get("status", "submitted"),
                "out": f"GPU job {job.get('status', 'submitted')} ({job.get('job_id')}, mode={mode})"
                       + (" — poll for result" if mode == "live" else " — dry-run only, no AWS launched")}

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
