"""Unit tests for the run_live output contract (contracts/run_live_schema.py)."""
from __future__ import annotations

import copy
import unittest

from contracts.run_live_schema import RUN_LIVE_SCHEMA, validate_run_live


def _minimal_valid() -> dict:
    """A minimal dict that conforms to the documented run_live contract."""
    return {
        "query": "Is TSC2 a viable target?",
        "plan": {
            "deliverable": "diligence", "disease": "tuberous sclerosis",
            "modality": "small molecule", "agents": [], "panel": [],
            "class": "diligence",
        },
        "priors": [],
        "discover": {
            "dossier": [
                {"value": "TSC2 loss activates mTOR", "source": "PMID:1",
                 "tier": "T2", "provenance": "emet-live"},
            ],
            "flags": {"VETO": [], "DIVERGENCE": [], "KNOWN_UNKNOWNS": []},
            "status": "complete",
            "agents": [{"id": "emet-runner", "status": "ok", "provenance": "emet-live"}],
        },
        "consult": {
            "round1": [
                {"persona": "KOL", "stance": "conditional",
                 "provenance": "persona-judgment", "status": "ok"},
            ],
            "round2": [],
            "spread": {"conviction_range": [3, 3], "stance_mix": {}, "moved_in_round2": 0,
                       "convergent_gate": ""},
        },
        "synthesize": {
            "recommendation": "Conditional advance", "confidence": "medium",
            "proposed_experiment": "Run orthogonal validation.", "entities": {},
        },
        "engagement_id": "eng_abc123",
        "reflection": {"engagement_id": "eng_abc123", "written": 3, "records": []},
        "_via": "harness-live",
    }


class TestRunLiveSchema(unittest.TestCase):

    def test_minimal_valid_conforms(self):
        self.assertEqual(validate_run_live(_minimal_valid()), [])

    def test_missing_required_top_level_key_fails(self):
        d = _minimal_valid()
        del d["discover"]
        errs = validate_run_live(d)
        self.assertTrue(any("discover" in e and "required" in e for e in errs), errs)

    def test_additive_top_level_keys_allowed(self):
        # serve.py stamps via / live; these MUST validate cleanly (additive contract).
        d = _minimal_valid()
        d["via"] = "engine-live"
        d["live"] = True
        self.assertEqual(validate_run_live(d), [])

    def test_fact_missing_provenance_fails(self):
        d = _minimal_valid()
        del d["discover"]["dossier"][0]["provenance"]
        errs = validate_run_live(d)
        self.assertTrue(any("provenance" in e and "required" in e for e in errs), errs)

    def test_written_must_be_int_not_bool(self):
        d = _minimal_valid()
        d["reflection"]["written"] = "lots"
        errs = validate_run_live(d)
        self.assertTrue(any("reflection.written" in e for e in errs), errs)

    def test_schema_is_additive_friendly(self):
        # The contract must NOT lock the top object — additive fields are part of the design.
        self.assertNotEqual(RUN_LIVE_SCHEMA.get("additionalProperties"), False)


if __name__ == "__main__":
    unittest.main()
