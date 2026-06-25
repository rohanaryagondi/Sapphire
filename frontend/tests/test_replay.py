"""Offline tests for the $0 deterministic replay of the captured real TSC2 run.

No model, no network — proves the frozen capture loads, conforms to the run_live contract,
and carries the real headline content (real moat + real EMET PMIDs + the spread + a DIVERGENCE).
"""
from __future__ import annotations

import os
import re
import sys
import unittest
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parents[1]
_ENGINE = _FRONTEND.parent / "sapphire-orchestrator"
for p in (str(_FRONTEND), str(_ENGINE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import bridge  # noqa: E402
from contracts.run_live_schema import validate_run_live  # noqa: E402


class TestReplay(unittest.TestCase):

    def setUp(self):
        self.r = bridge.replay("tsc2_live_run")

    def test_loads_and_conforms_to_contract(self):
        self.assertEqual(validate_run_live(self.r), [])
        self.assertEqual(self.r["_via"], "replay")
        self.assertTrue(self.r["_replay"])
        self.assertEqual(self.r["_elapsed_s"], 0.0)   # $0 / instant

    def test_real_emet_pmids_present(self):
        emet = [f for f in self.r["discover"]["dossier"] if f.get("provenance") == "emet-live"]
        pmids = sorted({m for f in emet for m in re.findall(r"PMID:\d+", f.get("source", ""))})
        self.assertGreaterEqual(len(pmids), 1)
        self.assertIn("PMID:22136276", pmids)         # a real captured PMID (EXIST-1)

    def test_real_internal_moat_present_and_tagged(self):
        moat = [f for f in self.r["discover"]["dossier"] if f.get("provenance") == "moat-real"]
        self.assertTrue(moat)
        self.assertTrue(all(f.get("plane") == "internal" for f in moat))
        self.assertTrue(self.r.get("_internal_only"))  # tagged internal-only

    def test_divergence_present(self):
        divs = self.r["discover"]["flags"]["DIVERGENCE"]
        self.assertTrue(divs)
        # Assert the CNS-RELEVANT divergence is captured (not just any non-empty list — two of the
        # three entries are lower-signal: a NurOwn/ALS corpus bleed and a FAERS-not-accessed gap).
        blob = " ".join(divs).lower()
        self.assertTrue(("tsc" in blob) or ("tuberous" in blob),
                        f"no TSC-relevant DIVERGENCE found in: {divs}")

    def test_the_spread_is_preserved(self):
        round1 = self.r["consult"]["round1"]
        self.assertGreaterEqual(len(round1), 3)
        stances = {v.get("stance") for v in round1}
        self.assertGreater(len(stances), 1)           # a real spread, not a single consensus

    def test_missing_scenario_returns_honest_error(self):
        r = bridge.replay("does_not_exist")
        self.assertEqual(r["_via"], "bridge-error")
        self.assertIn("discover", r)                  # well-formed, not a traceback

    def test_available_replays_lists_tsc2(self):
        self.assertIn("tsc2_live_run", bridge.available_replays())


if __name__ == "__main__":
    unittest.main()
