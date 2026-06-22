"""
tests/test_loop_demo.py — Offline tests for the Sapphire self-improvement loop.

Asserts:
  - Two run_engagement() calls accumulate memory records.
  - recall() surfaces prior conclusions across engagements.
  - record_outcome(..., refuted) opens a moat_blindspot.

Uses SAPPHIRE_ENGAGEMENTS_DIR + SAPPHIRE_MEMORY_DIR pointed at tempdirs
so the real RohanOnly store is never touched. $0 / offline / deterministic.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_loop_demo -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from engagement import run_engagement
from memory import recall, record_outcome, read_all


class TestLoopDemo(unittest.TestCase):

    def setUp(self):
        """Redirect all persistent writes to tempdirs."""
        self._eng_dir = tempfile.mkdtemp(prefix="sapphire_eng_")
        self._mem_dir = tempfile.mkdtemp(prefix="sapphire_mem_")
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem_dir

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    # ── helper ──────────────────────────────────────────────────────────────

    def _run_two_engagements(self):
        """Run nav1_8 and lrrk2_pd; return (r1, r2)."""
        r1 = run_engagement("nav1_8")
        r2 = run_engagement("lrrk2_pd")
        return r1, r2

    # ── test 1: memory accumulates across two engagements ───────────────────

    def test_memory_accumulates(self):
        """After two run_engagement calls, memory must contain records from both."""
        r1, r2 = self._run_two_engagements()
        refl1 = r1.get("reflection") or {}
        refl2 = r2.get("reflection") or {}
        # Each engagement should write ≥1 record (at least a conclusion).
        self.assertGreater(refl1.get("written", 0), 0,
                           "nav1_8 reflection wrote nothing")
        self.assertGreater(refl2.get("written", 0), 0,
                           "lrrk2_pd reflection wrote nothing")
        # Total store has records from both.
        all_recs = read_all()
        self.assertGreaterEqual(len(all_recs), 2,
                                f"Expected ≥2 memory records; got {len(all_recs)}")

    # ── test 2: conclusions are present in store ─────────────────────────────

    def test_conclusions_in_store(self):
        """Both engagements produce a 'conclusion' record."""
        self._run_two_engagements()
        conclusions = [r for r in read_all() if r["type"] == "conclusion"]
        self.assertGreaterEqual(len(conclusions), 2,
                                f"Expected ≥2 conclusions; got {len(conclusions)}")

    # ── test 3: recall surfaces priors by gene ───────────────────────────────

    def test_recall_by_gene(self):
        """recall({'genes': ['LRRK2']}) must return ≥1 record after lrrk2_pd."""
        self._run_two_engagements()
        hits = recall({"genes": ["LRRK2"]})
        self.assertGreater(len(hits), 0,
                           "recall(LRRK2) returned nothing after lrrk2_pd run")

    # ── test 4: recall surfaces priors by disease (nav1_8 tuberous sclerosis) -

    def test_recall_by_disease(self):
        """recall({'diseases': [...]}) returns ≥1 record if the disease was tagged."""
        self._run_two_engagements()
        # nav1_8 is SCN11A / neuropathic pain; tsc2 scenario tags tuberous sclerosis
        # Run tsc2 as well for this assertion.
        run_engagement("tsc2")
        hits_tsc = recall({"diseases": ["tuberous sclerosis / mTORopathy CNS"]})
        self.assertGreater(len(hits_tsc), 0,
                           "recall(tuberous sclerosis) returned nothing after tsc2 run")

    # ── test 5: record_outcome(refuted) opens a moat_blindspot ──────────────

    def test_refuted_outcome_opens_blindspot(self):
        """A refuted record_outcome must write a moat_blindspot to memory."""
        self._run_two_engagements()
        proposals = [r for r in read_all() if r["type"] == "experiment_proposal"]
        self.assertGreater(len(proposals), 0,
                           "No experiment_proposal found — can't test outcome")
        prop = proposals[0]
        before = len([r for r in read_all() if r["type"] == "moat_blindspot"])

        record_outcome(
            prop["id"],
            {
                "result": "refuted",
                "data": "moat under-detected the lung lysosomal window",
                "source": "wetlab-demo",
            },
        )

        after = [r for r in read_all() if r["type"] == "moat_blindspot"]
        self.assertGreater(len(after), before,
                           "Expected a new moat_blindspot; none appeared")

    # ── test 6: record_outcome(confirmed) does NOT open a blindspot ──────────

    def test_confirmed_outcome_no_blindspot(self):
        """A confirmed record_outcome must NOT write a moat_blindspot."""
        self._run_two_engagements()
        proposals = [r for r in read_all() if r["type"] == "experiment_proposal"]
        self.assertGreater(len(proposals), 0, "No proposals for confirmed test")
        prop = proposals[0]
        before = [r for r in read_all() if r["type"] == "moat_blindspot"]

        record_outcome(
            prop["id"],
            {
                "result": "confirmed",
                "data": "validated in disease model",
                "source": "wetlab-demo",
            },
        )

        after = [r for r in read_all() if r["type"] == "moat_blindspot"]
        self.assertEqual(len(after), len(before),
                         "Confirmed outcome should NOT create a moat_blindspot")

    # ── test 7: experiment_proposal records are present ──────────────────────

    def test_experiment_proposals_present(self):
        """run_engagement should write experiment_proposal records via reflect."""
        self._run_two_engagements()
        proposals = [r for r in read_all() if r["type"] == "experiment_proposal"]
        self.assertGreater(len(proposals), 0,
                           "Expected ≥1 experiment_proposal after two engagements")

    # ── test 8: recall returns records with correct schema ───────────────────

    def test_recall_record_schema(self):
        """Recalled records must have required fields: id, type, entities, payload."""
        self._run_two_engagements()
        all_recs = recall({"genes": ["LRRK2"]})
        for r in all_recs:
            for field in ("id", "type", "entities", "payload"):
                self.assertIn(field, r,
                              f"Recall record missing '{field}': {r}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
