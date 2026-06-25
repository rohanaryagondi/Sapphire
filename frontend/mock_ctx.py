"""Mock-backend ctx for the Demo profile — the SINGLE source of truth, reused from the
offline engine tests so the demo path and the test path can never drift.

`_build_ctx` (sapphire-orchestrator/tests/test_live_engine.py) wires in-process mocks for
claude / EMET / Q-Models / the network seams while keeping the REAL moat (if its SQLite is
present). The Demo profile runs `run_live` through exactly this ctx — deterministic, $0, no
external calls.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ENGINE = Path(__file__).resolve().parents[1] / "sapphire-orchestrator"


def _ensure_paths() -> None:
    """Engine + its tests dir on sys.path, at CALL time. Chainlit rebuilds sys.path between
    import and handler invocation, so a module-level insert would be gone; re-ensure here.
    Idempotent."""
    for p in (str(_ENGINE), str(_ENGINE / "tests")):
        if p not in sys.path:
            sys.path.insert(0, p)


def build_mock_ctx() -> dict:
    """Return the offline mock ctx used by the engine's own test suite (parity guaranteed)."""
    _ensure_paths()
    from test_live_engine import _build_ctx as _engine_build_ctx
    return _engine_build_ctx()
