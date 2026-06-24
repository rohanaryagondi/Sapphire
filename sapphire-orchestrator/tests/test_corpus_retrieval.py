"""Offline integration test: corpus-first retrieval lands in the dossier via run_live.

Proves the K2 wiring end-to-end against the REAL shipped FDA-memory corpus, with all
external backends (claude / emet / qmodels) mocked. $0, no network.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_corpus_retrieval -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

_PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sapphire-orchestrator/
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from corpus.reader import has_corpus  # noqa: E402
from live_engine import run_live  # noqa: E402
from tests.test_live_engine import _build_ctx  # noqa: E402


class TestCorpusRetrievalThroughRunLive(unittest.TestCase):

    def setUp(self):
        self._eng = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()
        if not has_corpus("fda-institutional-memory"):
            self.skipTest("fda-institutional-memory corpus not present")

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _run(self):
        return run_live(
            "Is aducanumab's accelerated approval for Alzheimer's amyloid a viable precedent?",
            ctx=_build_ctx(),
        )

    def test_corpus_fact_lands_in_dossier(self):
        result = self._run()
        dossier = result["discover"]["dossier"]
        corpus_facts = [f for f in dossier if f.get("provenance") == "corpus"]
        self.assertGreaterEqual(len(corpus_facts), 1,
                                "expected >=1 corpus-sourced fact in the dossier")
        # Each corpus fact carries its card's source/tier/url + the corpus marker.
        for f in corpus_facts:
            self.assertTrue(f.get("from_corpus"))
            self.assertIn("value", f)
            self.assertIn("source", f)
            self.assertIn("tier", f)
            self.assertEqual(f["field"], "fda-institutional-memory")

    def test_corpus_facts_do_not_create_a_veto(self):
        # A corpus card is a LEAD, not a dispositive veto — even decision=CRL/approval
        # cards must NOT populate the VETO flag list from the corpus path.
        result = self._run()
        corpus_values = {
            f["value"] for f in result["discover"]["dossier"]
            if f.get("provenance") == "corpus"
        }
        self.assertTrue(corpus_values)  # we did surface corpus facts
        for v in result["discover"]["flags"]["VETO"]:
            self.assertNotIn(v, corpus_values,
                             "a corpus card must not become a VETO flag")

    def test_corpus_retrieval_is_traced(self):
        result = self._run()
        eid = result["engagement_id"]
        trace_path = os.path.join(self._eng, eid, "trace.jsonl")
        with open(trace_path, encoding="utf-8") as fh:
            events = [json.loads(l) for l in fh if l.strip()]
        corpus_events = [e for e in events if e.get("type") == "corpus_retrieval"]
        self.assertTrue(corpus_events, "corpus retrieval must be traced")
        self.assertTrue(any(e["agent_id"] == "fda-institutional-memory" and e["n_cards"] >= 1
                            for e in corpus_events))

    def test_provenance_label_is_allowed(self):
        from contracts.provenance import is_valid_provenance
        self.assertTrue(is_valid_provenance("corpus"))


if __name__ == "__main__":
    unittest.main()
