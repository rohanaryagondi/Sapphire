import unittest
from emet.adapter import normalize_emet
from contracts.jsonschema_min import validate
from harness.contracts import resolve

ENVELOPE = {
    "candidate": "SCN11A",
    "emet_workflow": "Target Validation",
    "verdict": "pass",
    "evidence": [
        {"claim": "GoF mutations validate analgesia", "source": "X et al, Nature 2016", "id_or_url": "PMID:26243570"},
        {"claim": "restricted peripheral expression", "source": "Y et al, 2019", "id_or_url": "PMID:31551682"},
    ],
    "notes": "",
    "chat_url": "https://app.summit-prod.benchsci.com/chat/abc",
    "captured_at": "2026-06-21T00:00:00Z",
    "provenance": "emet-live",
}

class TestAdapter(unittest.TestCase):
    def test_evidence_becomes_t2_cited_facts(self):
        out = normalize_emet(ENVELOPE)
        self.assertEqual(out["candidate"], "SCN11A")
        self.assertEqual(len(out["facts"]), 2)
        self.assertTrue(all(f["tier"] == "T2" for f in out["facts"]))
        self.assertIn("PMID:26243570", out["facts"][0]["source"])
        self.assertEqual(out["provenance"], "emet-live")

    def test_pass_adds_no_flag(self):
        out = normalize_emet(ENVELOPE)
        self.assertTrue(all("flag" not in f for f in out["facts"]))

    def test_flag_verdict_appends_known_unknown(self):
        env = dict(ENVELOPE, verdict="flag", notes="thin, conflicting reports")
        out = normalize_emet(env)
        flags = [f.get("flag") for f in out["facts"]]
        self.assertIn("KNOWN_UNKNOWN", flags)

    def test_no_go_appends_contraindication_without_veto(self):
        env = dict(ENVELOPE, verdict="no_go", notes="cardiac liability")
        out = normalize_emet(env)
        self.assertNotIn("VETO", [f.get("flag") for f in out["facts"]])      # EMET never vetoes
        self.assertTrue(any("cardiac liability" in f["value"] for f in out["facts"]))

    def test_output_validates_against_findings_schema(self):
        out = normalize_emet(ENVELOPE)
        schema = resolve("emet-runner").output_schema     # the findings schema
        self.assertEqual(validate(out, schema, schema), [])

    def test_empty_evidence_pass_is_valid(self):
        env = dict(ENVELOPE, evidence=[], verdict="pass")
        out = normalize_emet(env)
        schema = resolve("emet-runner").output_schema
        self.assertEqual(validate(out, schema, schema), [])

    def test_none_claim_becomes_empty_string_and_validates(self):
        env = dict(ENVELOPE, evidence=[{"claim": None, "source": "X", "id_or_url": "PMID:1"}])
        out = normalize_emet(env)
        self.assertIsInstance(out["facts"][0]["value"], str)
        schema = resolve("emet-runner").output_schema
        self.assertEqual(validate(out, schema, schema), [])

    def test_no_go_empty_chat_url_keeps_nonempty_source(self):
        env = dict(ENVELOPE, verdict="no_go", notes="cardiac liability", chat_url="")
        out = normalize_emet(env)
        self.assertTrue(all(f["source"].strip() for f in out["facts"]))   # no empty source anywhere
        schema = resolve("emet-runner").output_schema
        self.assertEqual(validate(out, schema, schema), [])

if __name__ == "__main__":
    unittest.main()
