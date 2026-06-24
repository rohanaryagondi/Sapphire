"""Offline tests for frontend/bridge.py — the in-process run_live seam.

Uses mock=True (the offline mock ctx), so $0, no network, deterministic. Isolates
engagement/memory writes to temp dirs.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parents[1]
_ENGINE = _FRONTEND.parent / "sapphire-orchestrator"
for p in (str(_FRONTEND), str(_ENGINE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import bridge  # noqa: E402
from contracts.run_live_schema import validate_run_live  # noqa: E402


class TestBridge(unittest.TestCase):
    def setUp(self):
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_run_mock_conforms_to_contract(self):
        r = bridge.run("Is TSC2 a viable target in tuberous sclerosis?", mock=True)
        # validate_run_live ignores additive keys (_elapsed_s, _mock) — additive contract.
        self.assertEqual(validate_run_live(r), [])
        self.assertIn("_elapsed_s", r)
        self.assertTrue(r["_mock"])
        self.assertEqual(r["_via"], "harness-live")

    def test_empty_query_does_not_crash(self):
        # An empty query never raises. The engine treats it as a general-CNS run (not a
        # degraded/zero-fact result), so assert the contract-valid shape + that the firm
        # really ran (_via harness-live, not a bridge error) — not a vacuous "is a dict".
        r = bridge.run("", mock=True)
        self.assertEqual(validate_run_live(r), [])
        self.assertEqual(r["_via"], "harness-live")

    def test_sequences_forwarded_to_run_live(self):
        # The bridge must accept and forward `sequences` (the ASO-Design handoff), not drop it.
        captured = {}
        import live_engine
        orig = live_engine.run_live

        def _spy(query, *, sequences=None, ctx=None, **kw):
            captured["sequences"] = sequences
            return orig(query, sequences=sequences, ctx=ctx, **kw)

        live_engine.run_live = _spy
        try:
            r = bridge.run("screen this ASO", mock=True, sequences=["GCACTTGAATTTCACGTTGT"])
        finally:
            live_engine.run_live = orig
        self.assertEqual(captured["sequences"], ["GCACTTGAATTTCACGTTGT"])
        self.assertEqual(validate_run_live(r), [])

    def test_build_ctx_live_is_none(self):
        self.assertIsNone(bridge.build_ctx(False))
        self.assertIsInstance(bridge.build_ctx(True), dict)

    def test_bridge_error_envelope_is_wellformed(self):
        env = bridge._error_envelope("q", RuntimeError("boom"))
        self.assertEqual(validate_run_live(env), [])
        self.assertEqual(env["_via"], "bridge-error")
        self.assertIn("boom", env["discover"]["flags"]["KNOWN_UNKNOWNS"][0])


if __name__ == "__main__":
    unittest.main()
