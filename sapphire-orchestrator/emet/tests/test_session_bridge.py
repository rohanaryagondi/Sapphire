"""Offline tests for the in-session EMET bridge (emet/session_bridge.py).

No live browser — a captured envelope stands in for what the orchestrator captures from its own
authenticated session. Proves: a covered candidate's real PMIDs become emet-live findings; an
uncovered candidate abstains honestly (never fabricated); and the handler injects through run_live.
"""
from __future__ import annotations

import unittest

from harness.contracts import Contract
from harness.errors import HarnessEscalation
from emet.session_bridge import make_session_emet_handler

C = Contract(id="emet-runner", role="", kind="emet-playwright", provenance_label="emet-live")

TSC2_ENVELOPE = {
    "candidate": "TSC2",
    "emet_workflow": "Target Validation",
    "verdict": "pass",
    "evidence": [
        {"claim": "TSC2 loss-of-function de-represses mTORC1 signaling in tuberous sclerosis.",
         "source": "Author, Journal 2018", "id_or_url": "PMID:29643504"},
        {"claim": "mTOR inhibition (everolimus) reduces SEGA tumor volume in TSC patients.",
         "source": "Franz, Lancet 2013", "id_or_url": "PMID:23158522"},
    ],
    "notes": "",
    "chat_url": "https://emet.benchsci.com/chat/abc",
    "captured_at": "2026-06-25T05:00:00Z",
    "provenance": "emet-live",
}


class TestSessionBridge(unittest.TestCase):

    def test_covered_candidate_returns_emet_live_findings(self):
        h = make_session_emet_handler({"TSC2": TSC2_ENVELOPE})
        out = h(C, {"candidate": "TSC2", "workflow": "Target Validation"})
        self.assertEqual(out["provenance"], "emet-live")
        self.assertTrue(out["facts"])
        # the real PMID is carried through into the cited source
        joined = " ".join(f["source"] for f in out["facts"])
        self.assertIn("PMID:29643504", joined)

    def test_case_tolerant_lookup(self):
        h = make_session_emet_handler({"tsc2": TSC2_ENVELOPE})
        out = h(C, {"candidate": "TSC2"})
        self.assertTrue(out["facts"])

    def test_uncovered_candidate_abstains_not_fabricates(self):
        h = make_session_emet_handler({"TSC2": TSC2_ENVELOPE})
        with self.assertRaises(HarnessEscalation) as cm:
            h(C, {"candidate": "KCNQ2"})        # no captured envelope
        self.assertEqual(cm.exception.code, "login-required")

    def test_empty_envelopes_abstains(self):
        h = make_session_emet_handler({})
        with self.assertRaises(HarnessEscalation):
            h(C, {"candidate": "TSC2"})


class TestSessionBridgeThroughRunLive(unittest.TestCase):
    """The injected session handler lands real EMET PMIDs in the dossier via run_live (offline)."""

    def setUp(self):
        import os
        import sys
        import tempfile
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()
        # make tests/_build_ctx importable
        _here = os.path.dirname(os.path.abspath(__file__))
        _pkg = os.path.dirname(os.path.dirname(_here))   # sapphire-orchestrator/
        for p in (_pkg, os.path.join(_pkg, "tests")):
            if p not in sys.path:
                sys.path.insert(0, p)

    def tearDown(self):
        import os
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_emet_pmid_lands_in_dossier(self):
        from test_live_engine import _build_ctx
        from live_engine import run_live
        ctx = _build_ctx()
        # Replace the offline mock emet handler with the in-session bridge holding a real envelope.
        ctx["emet_handler"] = make_session_emet_handler({"TSC2": TSC2_ENVELOPE})
        result = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=ctx)
        emet_facts = [f for f in result["discover"]["dossier"]
                      if f.get("provenance") == "emet-live"]
        self.assertTrue(emet_facts, "the session EMET handler must land emet-live facts")
        joined = " ".join(f.get("source", "") for f in emet_facts)
        self.assertIn("PMID:29643504", joined)   # the REAL PMID, not a fabricated one
        # EMET is the external plane.
        self.assertTrue(all(f.get("plane") == "external" for f in emet_facts))
        # emet-runner reported ok (fired), not abstained.
        agents = {a["id"]: a["status"] for a in result["discover"]["agents"]}
        self.assertEqual(agents.get("emet-runner"), "ok")


if __name__ == "__main__":
    unittest.main()
