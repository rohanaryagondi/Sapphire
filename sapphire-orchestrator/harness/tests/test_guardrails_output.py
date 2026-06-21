import unittest
from harness.contracts import Contract
from harness.guardrails import (facts_only_cited, must_cite_dossier, veto_is_gate,
                                emet_tab_discipline, stamp_provenance)

C = Contract(id="x", role="", kind="claude-subagent", provenance_label="emet-live")

class TestOutputGuards(unittest.TestCase):
    def test_facts_uncited_row_violates(self):
        out = {"facts": [{"value": "GoF", "source": "", "tier": "T2"}]}
        self.assertTrue(facts_only_cited(C, out, {}))

    def test_facts_cited_row_passes(self):
        out = {"facts": [{"value": "GoF", "source": "PMID:1", "tier": "T2"}]}
        self.assertEqual(facts_only_cited(C, out, {}), [])

    def test_veto_must_be_tier_t1(self):
        out = {"facts": [{"value": "prior CRL", "source": "PMID:9", "tier": "T2", "flag": "VETO"}]}
        self.assertTrue(facts_only_cited(C, out, {}))   # VETO at T2 → violation

    def test_must_cite_dossier_unanchored_violates(self):
        out = {"fact_claims": [{"claim": "Nav1.5 risk", "cite": "Z9"}]}
        self.assertTrue(must_cite_dossier(C, out, {"dossier_fields": ["B1", "C3"]}))

    def test_must_cite_dossier_anchored_passes(self):
        out = {"fact_claims": [{"claim": "Nav1.5 risk", "cite": "C3"}]}
        self.assertEqual(must_cite_dossier(C, out, {"dossier_fields": ["B1", "C3"]}), [])

    def test_veto_is_gate_blocks_silent_drop(self):
        out = {"stance": "no_go", "action": "drop"}
        self.assertTrue(veto_is_gate(C, out, {}))

    def test_veto_is_gate_surfaced_ok(self):
        out = {"stance": "no_go", "action": "surface"}
        self.assertEqual(veto_is_gate(C, out, {}), [])

    def test_emet_tab_discipline_requires_facts(self):
        self.assertTrue(emet_tab_discipline(C, {"candidate": "SCN11A"}, {}))
        self.assertEqual(emet_tab_discipline(C, {"candidate": "SCN11A", "facts": []}, {}), [])

    def test_stamp_provenance_sets_label(self):
        out = stamp_provenance(C, {"facts": [{"value": "x", "source": "s", "tier": "T1"}]})
        self.assertEqual(out["provenance"], "emet-live")
        self.assertEqual(out["facts"][0]["provenance"], "emet-live")

if __name__ == "__main__":
    unittest.main()
