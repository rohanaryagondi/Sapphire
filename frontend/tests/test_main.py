"""Offline tests for frontend/main.py profile → bridge.run kwargs mapping (imports chainlit)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parents[1]
if str(_FRONTEND) not in sys.path:
    sys.path.insert(0, str(_FRONTEND))

import main  # noqa: E402  (registers chainlit handlers; importable headless)


class TestProfileKwargs(unittest.TestCase):
    def test_demo_is_mock(self):
        self.assertEqual(main._profile_run_kwargs(main.DEMO_PROFILE), {"mock": True, "model": None})

    def test_cheap_is_real_haiku(self):
        kw = main._profile_run_kwargs(main.CHEAP_PROFILE)
        self.assertFalse(kw["mock"])
        self.assertEqual(kw["model"], main.CHEAP_MODEL)
        self.assertNotIn("simulate", kw)            # cheap runs REAL models

    def test_simulate_profile_real_backends_simulated_models(self):
        kw = main._profile_run_kwargs(main.SIMULATE_PROFILE)
        self.assertFalse(kw["mock"])                # real moat/EMET/seams
        self.assertTrue(kw["simulate"])             # but claude-subagent reasoning is 🧪 simulated
        self.assertEqual(kw["model"], main.CHEAP_MODEL)

    def test_simulate_banner_is_clearly_labeled(self):
        self.assertIn("🧪", main.SIMULATE_BANNER)
        self.assertIn("SIMULATED", main.SIMULATE_BANNER)


if __name__ == "__main__":
    unittest.main()
