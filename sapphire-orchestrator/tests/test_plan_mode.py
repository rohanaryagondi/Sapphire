"""Offline tests for plan_mode and approved_plan integration in live_engine.run_live.

All real backends (claude, emet, aws) are replaced with in-process mocks.
smart_plan is mocked via mock.patch to avoid live LLM calls.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_plan_mode -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from live_engine import run_live, _BUCKET1_AGENTS
from smart_plan import SmartPlanError
from harness.contracts import load_registry
from tests.test_live_engine import _build_ctx


def _smart_plan_result(registry=None):
    """A valid mock smart_plan result selecting 'emet-runner' and 'clinical-trial-registry'."""
    known_ids = None
    if registry is not None:
        known_ids = {a["id"] for a in registry.get("agents", [])}
    # Select the first two agents from _BUCKET1_AGENTS that are in the registry.
    if known_ids:
        universe = [aid for aid in _BUCKET1_AGENTS if aid in known_ids]
    else:
        universe = list(_BUCKET1_AGENTS)
    # Try to use emet-runner + clinical-trial-registry if available; else first two.
    preferred = ["emet-runner", "clinical-trial-registry"]
    selected = [aid for aid in preferred if aid in universe]
    if not selected:
        selected = universe[:2]
    dropped = [aid for aid in universe if aid not in selected]
    return {
        "selected_agents": [{"id": aid, "why": "test selection"} for aid in selected],
        "dropped_agents": [{"id": aid, "why": "lower priority"} for aid in dropped],
        "panel_rationale": "Focus on live evidence and trials for this query.",
        "notes": "offline test mock",
    }


class TestPlanMode(unittest.TestCase):

    def setUp(self):
        """Use temp dirs so tests never touch the real engagements / memory stores."""
        self._eng_dir = tempfile.mkdtemp()
        self._mem_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir
        # Enable simulation mode so claude-subagent dispatches are fast ($0, offline).
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        self._registry = load_registry()

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)
        os.environ.pop("SAPPHIRE_SIMULATE_MODELS", None)

    def _ctx(self):
        return _build_ctx()

    # ── test 1: llm+approve returns a pending plan, no agents ran ────────────
    def test_llm_approve_returns_pending_plan(self):
        """plan_mode='llm+approve' must:
          - return a dict with plan_pending_approval=True
          - NOT include 'discover' (no agents ran)
          - include engagement_id and plan
        """
        sp_result = _smart_plan_result(self._registry)
        with mock.patch("smart_plan.smart_plan", return_value=sp_result):
            result = run_live(
                "Is TSC2 viable in tuberous sclerosis?",
                plan_mode="llm+approve",
                ctx=self._ctx(),
            )
        self.assertTrue(result.get("plan_pending_approval") is True,
                        f"Expected plan_pending_approval=True; got {result.get('plan_pending_approval')}")
        self.assertNotIn("discover", result,
                         "'discover' must NOT be present — no agents should have run")
        self.assertIn("engagement_id", result)
        self.assertIn("plan", result)
        # smart_plan key present (LLM succeeded)
        self.assertIn("smart_plan", result)
        self.assertEqual(result.get("plan_source"), "llm")
        self.assertEqual(result.get("_via"), "harness-live-plan")

    # ── test 2: approved_plan runs exactly those agents ──────────────────────
    def test_approved_plan_runs_exactly_those_agents(self):
        """approved_plan=['emet-runner'] must run ONLY emet-runner.

        Verify via discover.agents containing exactly that id.
        """
        # Check emet-runner is in the registry before the test.
        known_ids = {a["id"] for a in self._registry.get("agents", [])}
        if "emet-runner" not in known_ids:
            self.skipTest("emet-runner not in registry — skipping")

        result = run_live(
            "Is TSC2 viable in tuberous sclerosis?",
            plan_mode="off",
            approved_plan=["emet-runner"],
            ctx=self._ctx(),
        )
        self.assertIn("discover", result)
        agent_ids = [a["id"] for a in result["discover"]["agents"]]
        self.assertIn("emet-runner", agent_ids,
                      f"emet-runner must appear in discover.agents; got {agent_ids}")
        # No other Bucket-1 agent should appear (rescue-mechanism is Bucket-1b, not Bucket-1).
        bucket1_other = [aid for aid in agent_ids
                         if aid in _BUCKET1_AGENTS and aid != "emet-runner"]
        self.assertEqual(bucket1_other, [],
                         f"Only emet-runner should run; unexpected: {bucket1_other}")
        self.assertEqual(result.get("plan_source"), "approved")

    # ── test 3: approved_plan silently drops unknown ids ────────────────────
    def test_approved_plan_filters_unknown_ids(self):
        """approved_plan with an unknown id → that id is silently dropped;
        only the known, in-bucket ids run."""
        known_ids = {a["id"] for a in self._registry.get("agents", [])}
        if "emet-runner" not in known_ids:
            self.skipTest("emet-runner not in registry — skipping")

        result = run_live(
            "Is TSC2 viable in tuberous sclerosis?",
            plan_mode="off",
            approved_plan=["emet-runner", "FAKE_AGENT_XYZ_NOT_IN_REGISTRY"],
            ctx=self._ctx(),
        )
        self.assertIn("discover", result)
        agent_ids = [a["id"] for a in result["discover"]["agents"]]
        self.assertNotIn("FAKE_AGENT_XYZ_NOT_IN_REGISTRY", agent_ids,
                         "Unknown id must be silently dropped from approved_plan")
        self.assertIn("emet-runner", agent_ids,
                      "Known id must still run after filtering")

    # ── test 4: plan_mode off matches default kwarg (structural regression floor) ─
    def test_plan_mode_off_matches_default_kwarg(self):
        """plan_mode='off' produces the same top-level keys as the no-kwarg call.

        Note: both runs post-PR include the new additive `plan_source` key (which
        was absent pre-PR).  Adding `plan_source` is an accepted additive change —
        callers that ignore unknown keys are unaffected.  This test is the structural
        regression floor (same keys, same plan_source value); it does not reproduce
        the pre-PR call signature because both sides of the comparison already have
        `plan_source` from this branch.
        """
        ctx_a = self._ctx()
        ctx_b = self._ctx()

        result_no_kwarg = run_live(
            "Is TSC2 viable in tuberous sclerosis?",
            ctx=ctx_a,
        )
        result_off = run_live(
            "Is TSC2 viable in tuberous sclerosis?",
            plan_mode="off",
            ctx=ctx_b,
        )
        keys_no_kwarg = set(result_no_kwarg.keys())
        keys_off = set(result_off.keys())
        self.assertEqual(keys_no_kwarg, keys_off,
                         f"plan_mode='off' must produce the same top-level keys as no kwarg.\n"
                         f"no-kwarg: {sorted(keys_no_kwarg)}\n"
                         f"off:      {sorted(keys_off)}")
        # Both should have plan_source="deterministic".
        self.assertEqual(result_no_kwarg.get("plan_source"), "deterministic")
        self.assertEqual(result_off.get("plan_source"), "deterministic")

    # ── test 5: plan_mode=llm stamps plan_source=llm in the result ──────────
    def test_llm_mode_stamps_plan_source(self):
        """plan_mode='llm' with a successful mock smart_plan → plan_source='llm' in result."""
        sp_result = _smart_plan_result(self._registry)
        with mock.patch("smart_plan.smart_plan", return_value=sp_result):
            result = run_live(
                "Is TSC2 viable in tuberous sclerosis?",
                plan_mode="llm",
                ctx=self._ctx(),
            )
        self.assertIn("discover", result,
                      "plan_mode='llm' must produce a full result with discover (agents ran)")
        self.assertEqual(result.get("plan_source"), "llm",
                         f"Expected plan_source='llm'; got {result.get('plan_source')}")
        # The agents that ran must be drawn from the LLM selection.
        agent_ids = {a["id"] for a in result["discover"]["agents"]}
        selected_ids = {a["id"] for a in sp_result["selected_agents"]}
        # Every ran agent must be in the LLM selection (or a non-Bucket-1 agent
        # like rescue-mechanism for rescue queries — none for a standard query).
        for aid in agent_ids:
            if aid in set(_BUCKET1_AGENTS):
                self.assertIn(aid, selected_ids,
                              f"agent {aid!r} ran but was not in LLM selection {selected_ids}")

    # ── test 6: llm fallback uses deterministic when smart_plan raises ───────
    def test_llm_fallback_uses_deterministic(self):
        """When smart_plan raises SmartPlanError, run_live falls back to deterministic:
          - plan_source='deterministic' in result
          - All known Bucket-1 agents appear in discover.agents (full panel ran)
        """
        with mock.patch("smart_plan.smart_plan",
                        side_effect=SmartPlanError("test fallback trigger")):
            result = run_live(
                "Is TSC2 viable in tuberous sclerosis?",
                plan_mode="llm",
                ctx=self._ctx(),
            )
        self.assertIn("discover", result,
                      "Fallback path must still produce a full result with discover")
        self.assertEqual(result.get("plan_source"), "deterministic",
                         f"Expected fallback plan_source='deterministic'; "
                         f"got {result.get('plan_source')}")
        # The full deterministic panel must have run (no agents dropped).
        agent_ids = {a["id"] for a in result["discover"]["agents"]}
        known_ids = {a["id"] for a in self._registry.get("agents", [])}
        for aid in _BUCKET1_AGENTS:
            if aid in known_ids:
                self.assertIn(aid, agent_ids,
                              f"Expected {aid!r} in discover.agents on deterministic fallback")

    # ── test 7: empty LLM selection falls back to deterministic ─────────────
    def test_empty_llm_selection_falls_back_to_deterministic(self):
        """When smart_plan returns selected_agents=[], live_engine must NOT run
        zero agents silently.  It must fall back to the full deterministic list
        and stamp plan_source='deterministic'.

        This guards against the degenerate case where the LLM legitimately
        over-prunes (e.g. on a meta-query) and produces an empty selection —
        running no Bucket-1 agents would yield a fact-free dossier, which is
        worse than a deterministic run.
        """
        empty_result = {
            "selected_agents": [],
            "dropped_agents": [{"id": aid, "why": "over-pruned"} for aid in _BUCKET1_AGENTS],
            "panel_rationale": "Nothing matched the query.",
            "notes": "empty selection — caller should fall back",
        }
        with mock.patch("smart_plan.smart_plan", return_value=empty_result):
            result = run_live(
                "Is TSC2 viable in tuberous sclerosis?",
                plan_mode="llm",
                ctx=self._ctx(),
            )
        self.assertIn("discover", result,
                      "Empty LLM selection must fall back to deterministic, not produce no facts")
        self.assertEqual(result.get("plan_source"), "deterministic",
                         f"Expected plan_source='deterministic' on empty LLM selection; "
                         f"got {result.get('plan_source')}")
        # The full deterministic panel must have run.
        agent_ids = {a["id"] for a in result["discover"]["agents"]}
        known_ids = {a["id"] for a in self._registry.get("agents", [])}
        for aid in _BUCKET1_AGENTS:
            if aid in known_ids:
                self.assertIn(aid, agent_ids,
                              f"Expected {aid!r} in discover.agents on empty-selection fallback")


if __name__ == "__main__":
    unittest.main()
