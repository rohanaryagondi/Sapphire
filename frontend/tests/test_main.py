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


class TestReplayProfiles(unittest.TestCase):
    """The session-bridge replay profile is registered and points at the captured session scenario."""

    def test_session_replay_scenario_constant(self):
        self.assertEqual(main.REPLAY_SESSION_SCENARIO, "tsc2_emet_session")

    def test_session_replay_profile_listed_in_chat_profiles(self):
        import asyncio
        profiles = {p.name for p in asyncio.run(main.chat_profiles())}
        self.assertIn(main.REPLAY_SESSION_PROFILE, profiles)
        self.assertIn(main.REPLAY_PROFILE, profiles)

    def test_session_scenario_is_an_available_replay(self):
        import bridge  # noqa
        from pathlib import Path
        scenario = (Path(__file__).resolve().parents[2] / "sapphire-orchestrator" /
                    "scenarios" / f"{main.REPLAY_SESSION_SCENARIO}.json")
        if not scenario.is_file():
            self.skipTest(f"{main.REPLAY_SESSION_SCENARIO}.json not captured yet "
                          "(run _build/capture_tsc2_emet_session.py)")
        self.assertIn(main.REPLAY_SESSION_SCENARIO, bridge.available_replays())


if __name__ == "__main__":
    unittest.main()
