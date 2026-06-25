"""
robyn_scs_seam.py — stdlib-only Sapphire seam for Robyn's SCS/STA neuronal-connectivity pipeline.

The Sapphire engine is stdlib-only. numpy/scipy/pandas + the vendored analysis code live in the
`tools/robyn_scs/firm_endpoint.py` subprocess; this module shells out and parses stdout JSON. No
third-party imports here.

Fire-when-relevant (honest): robyn_scs needs MATLAB-split imaging CSVs (a `<plate>/v17_traces/` dir
of FOV quartets). It fires ONLY when `inputs["robyn_scs"]` carries an `input_dir` pointing at such
data; for a standard target/diligence query (no imaging data) it returns `facts: []` (honest empty),
exactly like aso-tox with no sequences. It never fabricates a connectivity result.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess

_THIS = pathlib.Path(os.path.abspath(__file__))
# sapphire-orchestrator/tools/robyn_scs_seam.py → repo root is two levels up
_REPO_ROOT = _THIS.parent.parent.parent
_ENDPOINT = _REPO_ROOT / "tools" / "robyn_scs" / "firm_endpoint.py"
PROVENANCE = "robyn-scs"
_TIMEOUT_S = 600  # the pipeline is heavy; generous but bounded


def _empty(candidate: str) -> dict:
    return {"candidate": candidate, "facts": [], "provenance": PROVENANCE}


def _spec_from_inputs(inputs: dict):
    """Pull the robyn_scs request from Bucket-1 inputs. Accepts:
       inputs["robyn_scs"] = {"input_dir": "<plate>/", ...}  (or just a path string).
       Returns the request dict, or None when no robyn_scs data is present (→ honest empty)."""
    spec = (inputs or {}).get("robyn_scs")
    if not spec:
        return None
    if isinstance(spec, str):
        return {"input_dir": spec}
    if isinstance(spec, dict) and (spec.get("input_dir") or spec.get("fov_input_dir")):
        return spec
    return None


def findings(inputs: dict, *, runner=None) -> dict:
    """Bucket-1 fact source. Returns {candidate, facts, provenance}.

    `runner(req_json)->str` is injectable for offline tests (default shells to firm_endpoint.py).
    Honest empty when no robyn_scs imaging data is present; honest error fact (KNOWN_UNKNOWN) when
    the subprocess fails — never a fabricated connectivity result.
    """
    candidate = (inputs or {}).get("candidate") or (inputs or {}).get("target") or ""
    req = _spec_from_inputs(inputs)
    if req is None:
        return _empty(candidate)

    try:
        out = (runner or _default_runner)(json.dumps(req))
        resp = json.loads(out)
    except Exception as exc:
        return {"candidate": candidate, "provenance": PROVENANCE,
                "facts": [{"value": f"robyn_scs unavailable ({type(exc).__name__})",
                           "source": "robyn_scs pipeline", "tier": "T3", "flag": "KNOWN_UNKNOWN"}]}

    if not resp.get("ok"):
        return {"candidate": candidate, "provenance": PROVENANCE,
                "facts": [{"value": f"robyn_scs error: {resp.get('error', 'unknown')}",
                           "source": "robyn_scs pipeline", "tier": "T3", "flag": "KNOWN_UNKNOWN"}]}

    s = resp.get("summary", {}) or {}
    # Defensive honesty guard (belt-and-suspenders for the endpoint's own empty-plate check):
    # zero FOVs/quartets means the pipeline never ran on real data — abstain (KNOWN_UNKNOWN)
    # rather than emit a confidence-inflating "0 connections across 0 FOVs" T2 success fact.
    if not s.get("n_fovs") and not s.get("n_quartets"):
        return {"candidate": candidate, "provenance": PROVENANCE,
                "facts": [{"value": "robyn_scs: no FOV quartets in input — pipeline did not run",
                           "source": "robyn_scs pipeline", "tier": "T3", "flag": "KNOWN_UNKNOWN"}]}
    tiers = ", ".join(f"{k}:{v}" for k, v in (s.get("tiers") or {}).items())
    facts = [{
        "value": (f"robyn_scs connectivity: {s.get('n_connections', 0)} tiered connection(s) across "
                  f"{s.get('n_fovs', 0)} FOV(s); {s.get('n_neurons', 0)} classified neuron(s)"
                  + (f" ({tiers})" if tiers else "")),
        "source": "Quiver robyn_scs SCS/STA pipeline (imaging-derived)",
        "tier": "T2",
    }]
    failed = s.get("failed") or []
    if failed:
        facts.append({"value": f"robyn_scs: {len(failed)} FOV(s) failed and were skipped: {failed[:5]}",
                      "source": "robyn_scs pipeline", "tier": "T3", "flag": "KNOWN_UNKNOWN"})
    return {"candidate": candidate, "facts": facts, "provenance": PROVENANCE}


def _default_runner(req_json: str) -> str:
    proc = subprocess.run(
        ["python3", str(_ENDPOINT)],
        input=req_json, capture_output=True, text=True, timeout=_TIMEOUT_S,
        cwd=str(_REPO_ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"firm_endpoint exited {proc.returncode}: {(proc.stderr or '')[:200]}")
    # stdout's last non-empty line is the JSON summary (lazy heavy imports may warn earlier).
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("firm_endpoint produced no output")
    return lines[-1]
