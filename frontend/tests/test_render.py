"""Pure, server-less unit tests for frontend/render.py.

Anchored on the captured real mock-ctx fixture (fixtures/run_live_mock.json) for the
main-path column/shape assertions; edge branches the happy-path mock doesn't produce
(abstained agents, VETO/DIVERGENCE flags, round2) are exercised with small synthetic
inline dicts — clearly test inputs, never faked run outputs.

No Chainlit import — render.py is pure stdlib.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parents[1]
if str(_FRONTEND) not in sys.path:
    sys.path.insert(0, str(_FRONTEND))

import render  # noqa: E402

_FIXTURE = _FRONTEND / "tests" / "fixtures" / "run_live_mock.json"


def _load_fixture() -> dict:
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))


class TestDossierAndPlanes(unittest.TestCase):
    def setUp(self):
        self.result = _load_fixture()
        self.discover = self.result["discover"]

    def test_two_plane_sections_when_both_present(self):
        tables = render.render_dossier(self.discover)
        planes = {t["plane"] for t in tables}
        self.assertIn("internal", planes)
        self.assertIn("external", planes)
        # internal must render before external (fixed order)
        order = [t["plane"] for t in tables if t["plane"] in ("internal", "external")]
        self.assertEqual(order, ["internal", "external"])

    def test_dossier_columns_exact(self):
        tables = render.render_dossier(self.discover)
        self.assertTrue(tables)
        for t in tables:
            self.assertEqual(t["columns"],
                             ["value", "field", "tier", "provenance", "source", "flag"])

    def test_internal_facts_only_in_internal_section(self):
        tables = {t["plane"]: t for t in render.render_dossier(self.discover)}
        internal_vals = {r["value"] for r in tables["internal"]["rows"]}
        external_vals = {r["value"] for r in tables["external"]["rows"]}
        # the moat fact lives in internal, not external
        for f in self.discover["dossier"]:
            if f["plane"] == "internal":
                self.assertIn(f["value"], internal_vals)
                self.assertNotIn(f["value"], external_vals)

    def test_tier_and_provenance_verbatim(self):
        tables = render.render_dossier(self.discover)
        rendered = {(r["value"], r["tier"], r["provenance"])
                    for t in tables for r in t["rows"]}
        for f in self.discover["dossier"]:
            self.assertIn((f["value"], f["tier"], f["provenance"]), rendered)

    def test_empty_plane_section_omitted(self):
        # Only external facts → no internal section.
        discover = {"dossier": [
            {"value": "x", "source": "PMID:1", "tier": "T2",
             "provenance": "emet-live", "plane": "external"}]}
        tables = render.render_dossier(discover)
        self.assertEqual([t["plane"] for t in tables], ["external"])

    def test_unclassified_plane_surfaced_not_dropped(self):
        discover = {"dossier": [
            {"value": "weird", "source": "?", "tier": "T3",
             "provenance": "stub", "plane": "mystery"}]}
        tables = render.render_dossier(discover)
        self.assertEqual([t["plane"] for t in tables], ["unclassified"])
        self.assertEqual(tables[0]["rows"][0]["value"], "weird")


class TestAgentsRoster(unittest.TestCase):
    def test_columns_and_no_timing(self):
        result = _load_fixture()
        spec = render.render_agents(result["discover"]["agents"])
        self.assertEqual(spec["columns"], ["id", "status", "provenance"])
        self.assertNotIn("timing", spec["columns"])
        for r in spec["rows"]:
            self.assertNotIn("timing", r)

    def test_abstained_agent_shown_explicitly(self):
        agents = [
            {"id": "emet-runner", "status": "escalated", "provenance": "emet-live"},
            {"id": "moat", "status": "ok", "provenance": "moat-real"},
        ]
        spec = render.render_agents(agents)
        statuses = {r["id"]: r["status"] for r in spec["rows"]}
        self.assertEqual(statuses["emet-runner"], "escalated")  # not hidden
        self.assertEqual(spec["n_abstained"], 1)


class TestFlags(unittest.TestCase):
    def test_empty_flags_render_nothing(self):
        self.assertEqual(
            render.render_flags({"VETO": [], "DIVERGENCE": [], "KNOWN_UNKNOWNS": []}), [])

    def test_veto_and_divergence_callouts(self):
        flags = {"VETO": ["aducanumab precedent"],
                 "DIVERGENCE": ["moat vs literature on TSC2"],
                 "KNOWN_UNKNOWNS": ["BBB penetration unknown"]}
        out = render.render_flags(flags)
        levels = {f["level"] for f in out}
        self.assertEqual(levels, {"VETO", "DIVERGENCE", "KNOWN_UNKNOWNS"})
        veto = next(f for f in out if f["level"] == "VETO")
        self.assertIn("aducanumab precedent", veto["items"])


class TestRoundtableSpread(unittest.TestCase):
    def setUp(self):
        self.result = _load_fixture()

    def test_one_card_per_persona_no_consensus_collapse(self):
        spec = render.render_roundtable(self.result["consult"])
        self.assertEqual(len(spec["round1"]), len(self.result["consult"]["round1"]))
        self.assertEqual(spec["n_personas"], len(self.result["consult"]["round1"]))

    def test_round2_absent_renders_round1_alone(self):
        spec = render.render_roundtable(self.result["consult"])
        self.assertFalse(spec["has_round2"])
        self.assertEqual(spec["round2"], [])

    def test_round2_progression_when_present(self):
        consult = {
            "round1": [{"persona": "KOL", "stance": "skeptic", "conviction": 2,
                        "status": "ok", "rationale": "thin", "fact_claims": []}],
            "round2": [{"persona": "KOL", "stance": "conditional", "conviction": 3,
                        "status": "ok", "rationale": "moved on rebuttal", "fact_claims": []}],
        }
        spec = render.render_roundtable(consult)
        self.assertTrue(spec["has_round2"])
        self.assertEqual(len(spec["round2"]), 1)
        self.assertEqual(spec["round2"][0]["stance"], "conditional")

    def test_fact_claims_passed_through_not_invented(self):
        consult = {"round1": [{"persona": "Payer", "stance": "conditional",
                               "conviction": 3, "status": "ok", "rationale": "r",
                               "fact_claims": [{"claim": "X", "cite": "PMID:1"}]}]}
        spec = render.render_roundtable(consult)
        self.assertEqual(spec["round1"][0]["fact_claims"], [{"claim": "X", "cite": "PMID:1"}])

    def test_spread_preserves_distinct_stances_no_collapse(self):
        # A genuine spread (distinct personas + stances) must render as distinct cards — proving
        # the render does NOT collapse to a consensus. (The captured mock fixture has identical
        # personas by construction, so a real-divergence test needs a synthetic input.)
        consult = {"round1": [
            {"persona": "Biotech CSO", "stance": "champion", "conviction": 4,
             "status": "ok", "rationale": "strong genetics", "fact_claims": []},
            {"persona": "Adversarial Red-Team", "stance": "veto", "conviction": 5,
             "status": "ok", "rationale": "BBB penetration unproven", "fact_claims": []},
            {"persona": "Payer", "stance": "conditional", "conviction": 2,
             "status": "ok", "rationale": "needs a biomarker", "fact_claims": []},
        ]}
        spec = render.render_roundtable(consult)
        personas = [c["persona"] for c in spec["round1"]]
        stances = [c["stance"] for c in spec["round1"]]
        self.assertEqual(len(spec["round1"]), 3)
        self.assertEqual(len(set(personas)), 3)          # distinct personas preserved
        self.assertGreater(len(set(stances)), 1)         # the spread is NOT collapsed to one stance
        self.assertIn("veto", stances)                   # the dissent survives


class TestStatusBanner(unittest.TestCase):
    def test_complete_run_no_banner(self):
        discover = {"status": "complete",
                    "flags": {"VETO": [], "DIVERGENCE": [], "KNOWN_UNKNOWNS": []}}
        self.assertIsNone(render.render_status(discover))

    def test_known_unknowns_trigger_partial_banner(self):
        discover = {"status": "complete-with-known-unknowns",
                    "flags": {"VETO": [], "DIVERGENCE": [],
                              "KNOWN_UNKNOWNS": ["abstained: emet-runner"]}}
        spec = render.render_status(discover)
        self.assertIsNotNone(spec)
        self.assertEqual(spec["kind"], "status")
        self.assertIn("Partial run", spec["title"])

    def test_status_banner_placed_before_roster_in_assembly(self):
        result = _load_fixture()
        result["discover"]["status"] = "complete-with-known-unknowns"
        result["discover"]["flags"]["KNOWN_UNKNOWNS"] = ["abstained: x"]
        kinds = [s["kind"] for s in render.render_run(result)]
        self.assertIn("status", kinds)
        self.assertLess(kinds.index("status"), kinds.index("agents"))


class TestSynthesisAndAssembly(unittest.TestCase):
    def setUp(self):
        self.result = _load_fixture()

    def test_synthesis_has_four_parts(self):
        spec = render.render_synthesis(self.result["synthesize"])
        for k in ("recommendation", "confidence", "proposed_experiment", "entities"):
            self.assertIn(k, spec)
        self.assertTrue(spec["recommendation"])

    def test_render_run_assembles_full_view_in_order(self):
        specs = render.render_run(self.result)
        kinds = [s["kind"] for s in specs]
        # header → plan → agents → dossier(s) → [flags] → roundtable → synthesis → footer
        self.assertEqual(kinds[0], "header")
        self.assertEqual(kinds[1], "plan")
        self.assertEqual(kinds[2], "agents")
        self.assertIn("dossier", kinds)
        self.assertIn("roundtable", kinds)
        self.assertIn("synthesis", kinds)
        self.assertEqual(kinds[-1], "footer")
        # dossier appears before roundtable before synthesis
        self.assertLess(kinds.index("dossier"), kinds.index("roundtable"))
        self.assertLess(kinds.index("roundtable"), kinds.index("synthesis"))

    def test_footer_surfaces_engagement_id(self):
        spec = render.render_footer(self.result["engagement_id"])
        self.assertEqual(spec["engagement_id"], self.result["engagement_id"])
        self.assertTrue(spec["engagement_id"].startswith("eng_"))

    def test_plan_lists_scoped_agents(self):
        spec = render.render_plan(self.result["plan"])
        self.assertTrue(spec["agents"])
        self.assertTrue(spec["panel"])

    def test_flags_render_between_dossier_and_roundtable_when_present(self):
        # The happy-path fixture has empty flags; inject one to verify the assembly places
        # the flag callout AFTER the dossier and BEFORE the roundtable (the integration path
        # the all-empty fixture leaves untested).
        result = _load_fixture()
        result["discover"]["flags"] = {
            "VETO": ["aducanumab precedent"], "DIVERGENCE": [], "KNOWN_UNKNOWNS": [],
        }
        kinds = [s["kind"] for s in render.render_run(result)]
        self.assertIn("flag", kinds)
        self.assertLess(kinds.index("dossier"), kinds.index("flag"))
        self.assertLess(kinds.index("flag"), kinds.index("roundtable"))


class TestAbstainedCount(unittest.TestCase):
    def test_blank_status_counted_as_not_ok(self):
        # Defensive: a missing/blank status (malformed envelope) must NOT be undercounted as ok.
        agents = [{"id": "a", "status": None, "provenance": "x"},
                  {"id": "b", "status": "ok", "provenance": "y"}]
        spec = render.render_agents(agents)
        self.assertEqual(spec["n_abstained"], 1)


if __name__ == "__main__":
    unittest.main()
