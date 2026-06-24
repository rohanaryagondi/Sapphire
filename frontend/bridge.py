"""In-process bridge: the seam between the Chainlit UI and Sapphire's live firm.

`run(query, *, mock)` calls `live_engine.run_live(query, ctx=...)` in-process and returns
the raw result dict (the documented `run_live` contract — see
`sapphire-orchestrator/contracts/run_live_schema.md`). The engine is **stdlib-only**, so
importing it here pulls in NO third-party package — chainlit/pandas stay frontend-only and
never leak into the engine.

- `mock=True`  → the offline mock ctx (Demo profile): deterministic, $0, no external calls.
- `mock=False` → `ctx=None` (Live profile): real backends. `run_live` needs the `claude` CLI
  for the live persona/fact subagents; without it those agents **abstain honestly** (the run
  is degraded, never fabricated, never a crash).

`run` never propagates an exception: `run_live` is contracted not to raise, and we wrap the
call so that even an import/setup failure returns an honest error envelope the UI renders as
an abstain — not a traceback in the user's face.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_ENGINE = Path(__file__).resolve().parents[1] / "sapphire-orchestrator"


def _ensure_engine_on_path() -> None:
    """Put the stdlib engine dir on sys.path. Called at CALL time (not just import) because
    Chainlit rebuilds sys.path between importing the app module and running the message
    handler — a module-level insert would be gone by the time `run()` executes (verified:
    onpath=False under chainlit). Idempotent.
    """
    if str(_ENGINE) not in sys.path:
        sys.path.insert(0, str(_ENGINE))


_ensure_engine_on_path()  # best-effort at import; run()/build_ctx re-ensure at call time


def build_ctx(mock: bool):
    """Demo → the offline mock ctx; Live → None (real backends)."""
    if not mock:
        return None
    _ensure_engine_on_path()
    from mock_ctx import build_mock_ctx
    return build_mock_ctx()


def _error_envelope(query: str, exc: Exception) -> dict:
    """An honest, well-formed degraded result when the bridge itself can't run the firm.

    Shaped like a minimal run_live dict so the renderer treats it as an empty/abstained run,
    never a fabricated answer.
    """
    return {
        "query": query,
        "plan": {"deliverable": "", "disease": "", "modality": "",
                 "agents": [], "panel": []},
        "priors": [],
        "discover": {
            "dossier": [],
            "flags": {"VETO": [], "DIVERGENCE": [],
                      "KNOWN_UNKNOWNS": [f"bridge error: {type(exc).__name__}: {exc}"]},
            "status": "bridge-error",
            "agents": [],
        },
        "consult": {"round1": []},
        "synthesize": {
            "recommendation": "Unavailable — the firm could not be convened (bridge error).",
            "confidence": "none",
            "proposed_experiment": "",
            "entities": {},
        },
        "engagement_id": "",
        "reflection": {"engagement_id": "", "written": 0, "records": []},
        "_via": "bridge-error",
        "_bridge_error": f"{type(exc).__name__}: {exc}",
    }


def run(query: str, *, mock: bool = True) -> dict:
    """Run the firm for `query` and return the run_live result dict (+ `_elapsed_s`).

    Never raises. On a hard failure returns `_error_envelope`. Adds a single TOTAL wall-clock
    (`_elapsed_s`) — per-agent timing is NOT available from the contract and is never faked.
    """
    started = time.monotonic()
    try:
        _ensure_engine_on_path()
        from live_engine import run_live
        result = run_live(query, ctx=build_ctx(mock))
    except Exception as exc:  # defensive — run_live is designed not to raise
        result = _error_envelope(query, exc)
    result["_elapsed_s"] = round(time.monotonic() - started, 2)
    result["_mock"] = bool(mock)
    return result
