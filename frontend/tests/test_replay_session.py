"""Offline tests for the $0 deterministic replay of the captured TSC2 session-bridge run.

No model, no network — proves the frozen session capture (tsc2_emet_session.json) loads, conforms
to the run_live contract, renders, and carries the real headline content captured via the front
end's real-EMET path: 9 real EMET PMIDs (driven live in the authenticated session, injected via
make_session_emet_handler) + real internal moat + the persona spread.
"""
from __future__ import annotations

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
import render  # noqa: E402
from contracts.run_live_schema import validate_run_live  # noqa: E402

_SCENARIO = "tsc2_emet_session"
_PATH = _ENGINE / "scenarios" / f"{_SCENARIO}.json"


@unittest.skipUnless(_PATH.is_file(),
                     f"{_SCENARIO}.json not captured (run _build/capture_tsc2_emet_session.py)")
class TestReplaySession(unittest.TestCase):

    def setUp(self):
        self.r = bridge.replay(_SCENARIO)

    def test_loads_and_conforms_to_contract(self):
        self.assertEqual(validate_run_live(self.r), [])
        self.assertEqual(self.r["_via"], "replay")
        self.assertTrue(self.r["_replay"])
        self.assertEqual(self.r["_elapsed_s"], 0.0)        # $0 / instant

    def test_nine_real_emet_pmids_present(self):
        emet = [f for f in self.r["discover"]["dossier"] if f.get("provenance") == "emet-live"]
        pmids = sorted({m for f in emet for m in re.findall(r"PMID:\d+", f.get("source", ""))})
        self.assertEqual(len(pmids), 9)                    # all 9 captured PMIDs
        self.assertIn("PMID:21329690", pmids)              # a real captured PMID (Han & Sahin)
        # EMET is the external plane.
        self.assertTrue(all(f.get("plane") == "external" for f in emet))

    def test_real_internal_moat_present_and_tagged(self):
        moat = [f for f in self.r["discover"]["dossier"] if f.get("provenance") == "moat-real"]
        self.assertTrue(moat)
        self.assertTrue(all(f.get("plane") == "internal" for f in moat))
        self.assertTrue(self.r.get("_internal_only"))      # tagged internal-only (real moat)

    def test_captured_via_session_bridge(self):
        # Honest labeling: the capture records it came through the session-bridge real-EMET path.
        self.assertEqual(self.r.get("_emet_session"), ["TSC2"])
        self.assertIn(self.r.get("_persona_mode"), ("haiku", "simulated"))

    def test_the_spread_is_preserved(self):
        round1 = self.r["consult"]["round1"]
        self.assertGreaterEqual(len(round1), 3)
        self.assertTrue(all(v.get("persona") for v in round1))

    def test_renders_without_error(self):
        specs = render.render_run(self.r)
        kinds = {s["kind"] for s in specs}
        # the core transparency regions are all present
        for k in ("header", "plan", "agents", "roundtable", "synthesis", "footer"):
            self.assertIn(k, kinds)
        # at least one dossier section (the two-plane split) rendered
        self.assertTrue(any(s["kind"] == "dossier" for s in specs))

    def test_listed_in_available_replays(self):
        self.assertIn(_SCENARIO, bridge.available_replays())


if __name__ == "__main__":
    unittest.main()
