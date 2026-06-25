"""Subprocess entrypoint for the Sapphire firm seam (heavy-deps side).

The Sapphire engine is stdlib-only; `sapphire-orchestrator/tools/robyn_scs_seam.py` shells out to
THIS script (which lazily pulls numpy/scipy/pandas via the vendored pipeline) and parses the JSON
summary from stdout. We do NOT reimplement anything — we call `endpoints.run_batch` / `run_fov` and
summarise the connectivity result into a small JSON the seam maps to dossier facts.

Usage (the seam invokes it; not a user CLI):
    echo '{"input_dir": "<plate>/", "scs_score_thresh": 0.7}' | python tools/robyn_scs/firm_endpoint.py
or for a single FOV:
    echo '{"fov_input_dir": "<plate>/"}' | python tools/robyn_scs/firm_endpoint.py   # first quartet only

Output (stdout): {"ok": true, "summary": {n_fovs, n_connections, n_neurons, tiers, failed}} or
{"ok": false, "error": "..."}.  Never raises into the caller — errors are returned as JSON.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def _summarise(batch: dict) -> dict:
    """Reduce a run_batch result to JSON-safe counts + tier breakdown (no DataFrames over the wire)."""
    merged = batch.get("merged_all")
    neurons = batch.get("neurons_all")
    n_conn = int(len(merged)) if merged is not None else 0
    n_neur = int(len(neurons)) if neurons is not None else 0
    tiers = {}
    # neuron_tiers tables carry a tier/class column in the vendored output; summarise if present.
    try:
        if neurons is not None and len(neurons):
            for col in ("tier", "neuron_tier", "class", "neuron_type"):
                if col in neurons.columns:
                    tiers = {str(k): int(v) for k, v in neurons[col].value_counts().to_dict().items()}
                    break
    except Exception:
        tiers = {}
    return {
        "n_fovs": len(batch.get("results", []) or []),
        "n_quartets": len(batch.get("quartets", []) or []),
        "n_connections": n_conn,
        "n_neurons": n_neur,
        "tiers": tiers,
        "failed": [f.get("fov", "") for f in (batch.get("failed", []) or [])],
    }


def main() -> int:
    try:
        req = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"bad json: {exc}"}))
        return 0
    try:
        import endpoints  # the vendored-wiring library (lazily pulls numpy/pandas/scipy)
        input_dir = req.get("input_dir") or req.get("fov_input_dir")
        if not input_dir:
            print(json.dumps({"ok": False, "error": "no input_dir provided"}))
            return 0
        kw = {k: req[k] for k in ("scs_score_thresh", "sta_score_thresh", "scs_min_ap", "sta_min_ap")
              if k in req}
        batch = endpoints.run_batch(input_dir, output_dir=req.get("output_dir"), **kw)
        print(json.dumps({"ok": True, "summary": _summarise(batch)}))
    except Exception as exc:  # never raise into the seam — honest error JSON
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
