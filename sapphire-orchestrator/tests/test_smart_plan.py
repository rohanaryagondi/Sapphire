"""Offline tests for smart_plan.py.

No live LLM calls — a mock runner is injected via ctx["runner"].

Run from sapphire-orchestrator/:
    python -m unittest tests.test_smart_plan -v
"""
from __future__ import annotations

import json
import os
import sys
import types
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from smart_plan import smart_plan, SmartPlanError
from live_engine import _BUCKET1_AGENTS
from harness.contracts import load_registry


def _make_runner(selected_ids: list[str], universe_ids: list[str]):
    """Return a mock runner that produces a valid smart_plan JSON response."""
    def _runner(cmd):
        obj = {
            "selected_agents": [{"id": aid, "why": "selected for test"} for aid in selected_ids],
            "dropped_agents": [
                {"id": aid, "why": "lower priority"}
                for aid in universe_ids if aid not in selected_ids
            ],
            "panel_rationale": "test rationale",
            "notes": "offline test",
        }
        return types.SimpleNamespace(
            stdout=json.dumps({"structured_output": obj}),
            returncode=0,
            stderr="",
        )
    return _runner


class TestSmartPlan(unittest.TestCase):

    def setUp(self):
        self._registry = load_registry()
        known_ids = {a["id"] for a in self._registry.get("agents", [])}
        self._universe = [aid for aid in _BUCKET1_AGENTS if aid in known_ids]

    # ── test 1: valid selection passes ───────────────────────────────────────
    def test_valid_selection_passes(self):
        """Mock runner returns a valid subset → smart_plan returns it without error;
        all selected_agents ids are in the candidate universe."""
        # Pick the first two agents from the universe as the selection.
        subset = self._universe[:2]
        ctx = {"runner": _make_runner(subset, self._universe)}
        result = smart_plan(
            "Is TSC2 viable in tuberous sclerosis?",
            {"deliverable": "diligence", "disease": "tuberous sclerosis"},
            self._registry,
            ctx,
        )
        self.assertIn("selected_agents", result)
        self.assertIn("dropped_agents", result)
        self.assertIn("panel_rationale", result)
        self.assertIn("notes", result)
        selected = [a["id"] for a in result["selected_agents"]]
        self.assertEqual(selected, subset, "returned ids must match what the runner produced")
        # All selected ids must be in the candidate universe (the key invariant).
        universe_set = set(self._universe)
        for aid in selected:
            self.assertIn(aid, universe_set,
                          f"selected agent {aid!r} not in the candidate universe")

    # ── test 2: hallucinated id raises ───────────────────────────────────────
    def test_hallucinated_id_raises(self):
        """Mock runner returns a JSON with an id NOT in the candidate universe →
        SmartPlanError('hallucinated agent id: ...') is raised."""
        def _runner_hallucinate(cmd):
            obj = {
                "selected_agents": [{"id": "totally-fake-agent-xyz", "why": "hallucinated"}],
                "dropped_agents": [],
                "panel_rationale": "test",
                "notes": "test",
            }
            return types.SimpleNamespace(
                stdout=json.dumps({"structured_output": obj}),
                returncode=0,
                stderr="",
            )
        ctx = {"runner": _runner_hallucinate}
        with self.assertRaises(SmartPlanError) as cm:
            smart_plan("test query", {}, self._registry, ctx)
        self.assertIn("hallucinated", str(cm.exception).lower(),
                      f"Expected 'hallucinated' in exception message; got {cm.exception}")

    # ── test 3: parse failure raises ─────────────────────────────────────────
    def test_parse_failure_raises(self):
        """Mock runner returns garbage stdout → SmartPlanError('unparseable...') raised."""
        def _runner_garbage(cmd):
            return types.SimpleNamespace(
                stdout="not json at all {{{{ BAD",
                returncode=0,
                stderr="",
            )
        ctx = {"runner": _runner_garbage}
        with self.assertRaises(SmartPlanError) as cm:
            smart_plan("test query", {}, self._registry, ctx)
        self.assertIn("unparseable", str(cm.exception).lower(),
                      f"Expected 'unparseable' in exception message; got {cm.exception}")

    # ── test 4: empty selection accepted ────────────────────────────────────
    def test_empty_selection_accepted(self):
        """Runner returns selected_agents=[] → accepted without error.

        The LLM may legitimately decide no agent is relevant (e.g. for a very
        abstract meta-query). Callers fall back to deterministic when they see
        an empty selection — smart_plan itself must not reject it.
        """
        def _runner_empty(cmd):
            obj = {
                "selected_agents": [],
                "dropped_agents": [
                    {"id": aid, "why": "not relevant to this abstract query"}
                    for aid in self._universe
                ],
                "panel_rationale": "Nothing in the universe matches this meta-query.",
                "notes": "caller should fall back to deterministic",
            }
            return types.SimpleNamespace(
                stdout=json.dumps({"structured_output": obj}),
                returncode=0,
                stderr="",
            )
        ctx = {"runner": _runner_empty}
        result = smart_plan("test abstract meta-query", {}, self._registry, ctx)
        self.assertEqual(result["selected_agents"], [],
                         "empty selection must be returned as-is")
        self.assertIn("panel_rationale", result)
        self.assertIn("notes", result)


if __name__ == "__main__":
    unittest.main()
