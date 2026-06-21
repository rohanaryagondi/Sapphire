import unittest
from contracts.jsonschema_min import validate
from contracts.schemas import EMET_ENVELOPE_SCHEMA, MEMORY_RECORD_SCHEMA, MEMORY_RECORD_TYPES
from contracts.provenance import is_valid_provenance

VALID_EMET = {
    "candidate": "SCN11A",
    "emet_workflow": "Target Validation",
    "verdict": "pass",
    "evidence": [{"claim": "GoF validates analgesia", "source": "X et al, Nature 2016", "id_or_url": "PMID:26243570"}],
    "notes": "",
    "chat_url": "https://app.summit-prod.benchsci.com/chat/abc",
    "captured_at": "2026-06-21T00:00:00Z",
    "provenance": "emet-live",
}

VALID_MEMORY = {
    "id": "mem_12ab34cd",
    "type": "conclusion",
    "engagement_id": "eng_99ff00aa",
    "ts": "2026-06-21T00:00:00Z",
    "entities": {"genes": ["SCN11A"], "smiles": [], "diseases": ["neuropathic pain"], "drugs": []},
    "payload": {"recommendation": "advance to cardiac-selectivity de-risking", "confidence": "conditional"},
    "provenance": "synthesis",
    "tier": "T2",
    "confidence": "high",
    "links": [],
    "supersedes": None,
}

class TestSchemas(unittest.TestCase):
    def test_valid_emet_envelope(self):
        self.assertEqual(validate(VALID_EMET, EMET_ENVELOPE_SCHEMA), [])

    def test_emet_bad_verdict_enum_caught(self):
        bad = dict(VALID_EMET, verdict="maybe")
        self.assertTrue(validate(bad, EMET_ENVELOPE_SCHEMA))

    def test_emet_missing_evidence_caught(self):
        bad = {k: v for k, v in VALID_EMET.items() if k != "evidence"}
        self.assertTrue(any("evidence: required" in e for e in validate(bad, EMET_ENVELOPE_SCHEMA)))

    def test_valid_memory_record(self):
        self.assertEqual(validate(VALID_MEMORY, MEMORY_RECORD_SCHEMA), [])

    def test_memory_bad_type_enum_caught(self):
        bad = dict(VALID_MEMORY, type="gossip")
        self.assertTrue(validate(bad, MEMORY_RECORD_SCHEMA))

    def test_memory_types_cover_spec(self):
        for t in ["fact", "conclusion", "experiment_proposal", "experiment_outcome",
                  "divergence", "persona_verdict", "calibration", "moat_blindspot"]:
            self.assertIn(t, MEMORY_RECORD_TYPES)

    def test_provenances_in_examples_are_valid(self):
        self.assertTrue(is_valid_provenance(VALID_EMET["provenance"]))
        self.assertTrue(is_valid_provenance(VALID_MEMORY["provenance"]))

if __name__ == "__main__":
    unittest.main()
