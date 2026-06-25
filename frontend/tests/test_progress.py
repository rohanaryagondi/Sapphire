"""Pure unit tests for frontend/progress.py — honest step labels/outputs (no chainlit)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parents[1]
if str(_FRONTEND) not in sys.path:
    sys.path.insert(0, str(_FRONTEND))

import progress  # noqa: E402


class TestProgress(unittest.TestCase):

    def test_plan_step(self):
        ev = {"stage": "plan", "phase": "done", "disease": "tuberous sclerosis",
              "modality": "small molecule", "agents": ["a", "b"], "panel": ["p"]}
        self.assertEqual(progress.step_name(ev), "Plan — scoping the engagement")
        out = progress.step_output(ev)
        self.assertIn("tuberous sclerosis", out)
        self.assertIn("2 fact agents", out)

    def test_bucket1_ok_shows_check_and_count(self):
        ev = {"stage": "bucket1", "phase": "done", "agent_id": "internal-science-lead",
              "status": "ok", "provenance": "moat-real", "n_facts": 8, "elapsed_s": 1.2}
        self.assertIn("Internal moat", progress.step_name(ev))
        out = progress.step_output(ev)
        self.assertTrue(out.startswith("✓"))
        self.assertIn("8 fact(s)", out)
        self.assertIn("moat-real", out)

    def test_bucket1_abstain_is_honest_not_a_check(self):
        ev = {"stage": "bucket1", "phase": "done", "agent_id": "emet-runner",
              "status": "escalated", "provenance": "emet-live", "n_facts": 0,
              "elapsed_s": 0.4, "error": "login-required"}
        out = progress.step_output(ev)
        self.assertNotIn("✓", out)            # an abstain/escalate NEVER shows a check
        self.assertIn("⚠", out)
        self.assertIn("escalated", out)
        self.assertIn("login-required", out)

    def test_roundtable_verdict_vs_abstain(self):
        ok = {"stage": "roundtable", "phase": "done", "agent_id": "KOL", "status": "ok",
              "stance": "conditional", "conviction": 3, "elapsed_s": 2.0}
        self.assertIn("conditional", progress.step_output(ok))
        self.assertIn("conviction 3", progress.step_output(ok))
        ab = {"stage": "roundtable", "phase": "done", "agent_id": "GP", "status": "abstained",
              "stance": "hold", "conviction": 0, "elapsed_s": 1.0}
        self.assertIn("abstained", progress.step_output(ab))
        self.assertNotIn("✓", progress.step_output(ab))

    def test_flags_and_synthesis(self):
        f = {"stage": "flags", "phase": "done", "n_veto": 1, "n_divergence": 2,
             "n_known_unknowns": 3}
        out = progress.step_output(f)
        self.assertIn("1 VETO", out)
        self.assertIn("2 DIVERGENCE", out)
        s = {"stage": "synthesis", "phase": "done", "recommendation": "Conditional advance",
             "confidence": "medium"}
        self.assertIn("Conditional advance", progress.step_output(s))
        self.assertIn("medium", progress.step_output(s))

    def test_parent_grouping(self):
        self.assertEqual(progress.parent_stage({"stage": "bucket1"}), "bucket1")
        self.assertEqual(progress.parent_stage({"stage": "roundtable"}), "roundtable")
        self.assertIsNone(progress.parent_stage({"stage": "plan"}))
        self.assertIsNone(progress.parent_stage({"stage": "synthesis"}))


if __name__ == "__main__":
    unittest.main()
