"""Offline unit tests for plan_narrative.build_deterministic_narrative.

Tests that the deterministic narrative helper produces a well-formed ``narrative``
dict (framing + 5 steps, correct plane/veto tagging, roundtable-on vs off) from a
synthetic plan — no network, no LLM.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_plan_narrative -v
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from plan_narrative import build_deterministic_narrative
from live_engine import _BUCKET1_AGENTS

_CANONICAL_KEYS = {"moat", "external", "veto", "roundtable", "synth"}


class TestDeterministicNarrative(unittest.TestCase):
    """Tests for the stdlib deterministic fallback narrative builder."""

    def _plan(self, disease="tuberous sclerosis", modality="ASO", deliverable="diligence"):
        return {"disease": disease, "modality": modality, "deliverable": deliverable}

    # ── test 1: basic structure ───────────────────────────────────────────────
    def test_returns_framing_and_five_steps(self):
        """build_deterministic_narrative must return a dict with 'framing' (non-empty str)
        and exactly 5 steps with the canonical keys."""
        result = build_deterministic_narrative(
            "Which genes rescue the TSC2 phenotype?",
            self._plan(),
            list(_BUCKET1_AGENTS),
            panel=["ex-fda-regulator", "adversarial-red-team", "payer", "kol"],
        )
        self.assertIsInstance(result, dict, "narrative must be a dict")
        self.assertIn("framing", result)
        self.assertIsInstance(result["framing"], str)
        self.assertTrue(len(result["framing"]) > 20,
                        f"framing must be a meaningful sentence; got {result['framing']!r}")
        self.assertIn("steps", result)
        steps = result["steps"]
        self.assertEqual(len(steps), 5,
                         f"Expected exactly 5 steps; got {len(steps)}: {[s['key'] for s in steps]}")
        step_keys = {s["key"] for s in steps}
        self.assertEqual(step_keys, _CANONICAL_KEYS,
                         f"Steps must have the 5 canonical keys; got {step_keys}")

    # ── test 2: step shapes ───────────────────────────────────────────────────
    def test_each_step_has_required_fields(self):
        """Every step must have 'key', 'title', 'prose' (non-empty strings)."""
        result = build_deterministic_narrative(
            "Is TSC2 a viable target?",
            self._plan(),
            list(_BUCKET1_AGENTS),
        )
        for step in result["steps"]:
            self.assertIn("key", step, f"Step missing 'key': {step}")
            self.assertIn("title", step, f"Step missing 'title': {step}")
            self.assertIn("prose", step, f"Step missing 'prose': {step}")
            self.assertIsInstance(step["key"], str)
            self.assertIsInstance(step["title"], str)
            self.assertIsInstance(step["prose"], str)
            self.assertTrue(len(step["prose"]) > 10,
                            f"Step prose must not be empty; step={step['key']!r}")

    # ── test 3: plane tagging ─────────────────────────────────────────────────
    def test_moat_step_has_internal_plane(self):
        """The 'moat' step must have plane='internal'."""
        result = build_deterministic_narrative(
            "Is TSC2 viable?",
            self._plan(),
            list(_BUCKET1_AGENTS),
        )
        moat = next(s for s in result["steps"] if s["key"] == "moat")
        self.assertEqual(moat.get("plane"), "internal",
                         f"moat step must have plane='internal'; got {moat.get('plane')!r}")

    def test_external_step_has_external_plane(self):
        """The 'external' step must have plane='external'."""
        result = build_deterministic_narrative(
            "Is TSC2 viable?",
            self._plan(),
            list(_BUCKET1_AGENTS),
        )
        ext = next(s for s in result["steps"] if s["key"] == "external")
        self.assertEqual(ext.get("plane"), "external",
                         f"external step must have plane='external'; got {ext.get('plane')!r}")

    # ── test 4: veto step tagging ─────────────────────────────────────────────
    def test_veto_step_references_veto_agents(self):
        """The 'veto' step prose/badges must reference fda-memory or patent-ip."""
        result = build_deterministic_narrative(
            "Is TSC2 viable?",
            self._plan(),
            list(_BUCKET1_AGENTS),
        )
        veto = next(s for s in result["steps"] if s["key"] == "veto")
        # At least one badge should carry a veto marker
        badges = veto.get("badges") or []
        prose = veto.get("prose", "")
        veto_mentioned = any("⛔" in b or "fda" in b.lower() or "patent" in b.lower()
                             for b in badges)
        veto_in_prose = ("fda" in prose.lower() or "patent" in prose.lower()
                         or "ip" in prose.lower())
        self.assertTrue(veto_mentioned or veto_in_prose,
                        f"veto step must reference fda or patent; badges={badges}, prose={prose!r}")

    # ── test 5: roundtable ON ─────────────────────────────────────────────────
    def test_roundtable_on_when_panel_given(self):
        """When panel is non-empty, the roundtable step must NOT describe it as skipped."""
        partners = ["ex-fda-regulator", "adversarial-red-team", "payer", "kol"]
        result = build_deterministic_narrative(
            "Is TSC2 viable?",
            self._plan(),
            list(_BUCKET1_AGENTS),
            panel=partners,
        )
        rt = next(s for s in result["steps"] if s["key"] == "roundtable")
        prose_lower = rt["prose"].lower()
        self.assertNotIn("skipped", prose_lower,
                         f"roundtable step must NOT say 'skipped' when panel present; got {rt['prose']!r}")
        # Should mention the number of partners or the partner names
        has_partner_mention = any(p.lower() in prose_lower for p in partners) or \
            str(len(partners)) in rt["prose"]
        self.assertTrue(has_partner_mention,
                        f"roundtable prose should mention partners; got {rt['prose']!r}")

    # ── test 6: roundtable OFF ────────────────────────────────────────────────
    def test_roundtable_off_when_panel_empty(self):
        """When panel is empty/None, the roundtable step must describe it as skipped."""
        result = build_deterministic_narrative(
            "Is TSC2 viable?",
            self._plan(),
            list(_BUCKET1_AGENTS),
            panel=[],
        )
        rt = next(s for s in result["steps"] if s["key"] == "roundtable")
        # Title or prose should mention 'skipped'
        skipped_mention = "skipped" in rt["title"].lower() or "skipped" in rt.get("prose", "").lower() \
                          or rt.get("skipping")
        self.assertTrue(skipped_mention,
                        f"roundtable step must indicate skipped when panel empty; got {rt!r}")

    # ── test 7: disease + modality from plan ─────────────────────────────────
    def test_framing_includes_plan_fields(self):
        """Framing must reference the disease and/or deliverable from the plan dict."""
        result = build_deterministic_narrative(
            "Is ALS viable?",
            {"disease": "ALS", "modality": "small-molecule", "deliverable": "diligence"},
            list(_BUCKET1_AGENTS),
        )
        framing = result["framing"]
        # At least one of disease/modality/deliverable should appear in framing
        found = ("ALS" in framing or "small-molecule" in framing or "diligence" in framing)
        self.assertTrue(found,
                        f"framing should reference plan fields; got {framing!r}")

    # ── test 8: no internal scores (values) in output ────────────────────────
    def test_no_internal_score_values_in_output(self):
        """Data boundary: no actual internal score *values* or model-specific field names
        should appear in the narrative. (Prose describing that scores stay inside the
        boundary is fine — we check for actual data-field names, not honesty statements.)"""
        # These are the actual field/column names from the internal moat schema.
        # They must never appear verbatim in a public-facing narrative.
        _FORBIDDEN = ["cosine", "ep_score", "cnsdp", "dfp_score", "reversal_strength"]
        result = build_deterministic_narrative(
            "Is TSC2 viable?",
            self._plan(),
            list(_BUCKET1_AGENTS),
        )
        blob = str(result).lower()
        for word in _FORBIDDEN:
            self.assertNotIn(word, blob,
                             f"Forbidden internal-score field name {word!r} found in narrative")

    # ── test 9: badges are lists of strings ──────────────────────────────────
    def test_badges_are_string_lists(self):
        """Any 'badges' field must be a list of strings."""
        result = build_deterministic_narrative(
            "Is TSC2 viable?",
            self._plan(),
            list(_BUCKET1_AGENTS),
        )
        for step in result["steps"]:
            if "badges" in step:
                self.assertIsInstance(step["badges"], list,
                                      f"badges must be a list; step={step['key']!r}")
                for b in step["badges"]:
                    self.assertIsInstance(b, str,
                                          f"each badge must be a str; step={step['key']!r}, badge={b!r}")

    # ── test 10: subset of agents (fewer external) ────────────────────────────
    def test_works_with_subset_of_agents(self):
        """Works correctly when only a subset of _BUCKET1_AGENTS is passed."""
        subset = ["internal-science-lead", "emet-runner", "fda-institutional-memory", "patent-ip"]
        result = build_deterministic_narrative(
            "Is TSC2 viable?",
            self._plan(),
            subset,
        )
        self.assertEqual(len(result["steps"]), 5)
        # External step should reflect only emet-runner (not the full panel)
        ext = next(s for s in result["steps"] if s["key"] == "external")
        # The step should mention 1 agent (emet-runner) not the full 15+
        self.assertIn("1 agent", ext["prose"] or "")


if __name__ == "__main__":
    unittest.main()
