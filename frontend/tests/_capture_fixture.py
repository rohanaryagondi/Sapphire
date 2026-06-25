"""Capture a real mock-ctx run_live output as the render-contract fixture.

The fixture (`fixtures/run_live_mock.json`) is the *real shape* the render helpers map —
captured, never hand-edited (provenance honesty). Edge branches the happy-path mock ctx
doesn't exercise (abstained agents, VETO/DIVERGENCE flags, round2) are tested with small
synthetic inline dicts in test_render.py, not by faking a run output here.

Run from the repo root:
    python frontend/tests/_capture_fixture.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_ENGINE = _REPO / "sapphire-orchestrator"
sys.path.insert(0, str(_ENGINE))
sys.path.insert(0, str(_ENGINE / "tests"))

# Isolate engagement/memory writes to temp dirs (don't touch the repo stores).
os.environ.setdefault("SAPPHIRE_ENGAGEMENTS_DIR", tempfile.mkdtemp())
os.environ.setdefault("SAPPHIRE_MEMORY_DIR", tempfile.mkdtemp())

from test_live_engine import _build_ctx  # noqa: E402
from live_engine import run_live  # noqa: E402
from contracts.run_live_schema import validate_run_live  # noqa: E402

QUERY = "Is TSC2 a viable target in tuberous sclerosis?"


def main() -> int:
    result = run_live(QUERY, ctx=_build_ctx())
    errs = validate_run_live(result)
    if errs:
        print("FAIL: captured output does not conform to run_live contract:", errs)
        return 1
    out = Path(__file__).resolve().parent / "fixtures" / "run_live_mock.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"captured -> {out}  (validate_run_live == [])")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
