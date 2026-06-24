"""Unit tests for corpus.reader — stdlib corpus-first retrieval.

Uses a self-contained fixture corpus written to a temp dir (no dependence on the
shipped FDA corpus), plus one assertion against the real FDA-memory corpus to prove
the reader reads the format that actually ships.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(os.path.dirname(_HERE))  # sapphire-orchestrator/
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from corpus.reader import read_corpus, has_corpus  # noqa: E402


def _write_corpus(base: Path, agent_id: str, cards: list[dict]) -> None:
    d = base / agent_id
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "index.jsonl", "w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c) + "\n")


_CARDS = [
    {"claim": "FDA granted accelerated approval to aducanumab for Alzheimer's on amyloid plaque reduction.",
     "drug": "aducanumab", "indication": "Alzheimer's disease", "decision": "approval",
     "source": "FDA memo", "url": "https://fda.gov/x", "tier": "T1"},
    {"claim": "FDA issued a CRL for pimavanserin in dementia-related psychosis.",
     "drug": "pimavanserin", "indication": "dementia psychosis", "decision": "CRL",
     "source": "Acadia PR", "url": "https://acadia.com/y", "tier": "T2"},
    {"claim": "Tofersen for SOD1 ALS received accelerated approval on a neurofilament biomarker.",
     "drug": "tofersen", "indication": "SOD1 ALS", "decision": "approval",
     "source": "FDA", "url": "https://fda.gov/z", "tier": "T1"},
]


class TestReader(unittest.TestCase):

    def setUp(self):
        self._base = Path(tempfile.mkdtemp())
        _write_corpus(self._base, "fixture-agent", _CARDS)

    def test_no_corpus_dir_returns_empty(self):
        self.assertFalse(has_corpus("nonexistent-agent", base_dir=self._base))
        self.assertEqual(read_corpus("nonexistent-agent", "anything", base_dir=self._base), [])

    def test_match_ranks_by_overlap(self):
        hits = read_corpus("fixture-agent",
                           "Is aducanumab's amyloid accelerated approval for Alzheimer's a precedent?",
                           base_dir=self._base)
        self.assertGreaterEqual(len(hits), 1)
        # The aducanumab/Alzheimer's/amyloid card must rank first.
        self.assertIn("aducanumab", hits[0]["claim"].lower())
        # Scores are present and non-increasing.
        scores = [h["_score"] for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_entities_contribute_terms(self):
        # Query text alone has no drug name; the entity supplies it.
        hits = read_corpus("fixture-agent", "what precedent applies?",
                           {"drugs": ["tofersen"], "diseases": ["ALS"]}, base_dir=self._base)
        self.assertTrue(any("tofersen" in h["claim"].lower() for h in hits))

    def test_no_match_returns_empty(self):
        hits = read_corpus("fixture-agent", "quantum chromodynamics lattice gauge theory",
                           base_dir=self._base)
        self.assertEqual(hits, [])

    def test_empty_query_returns_empty(self):
        # No query terms (all stopwords / too short) → honest empty, no fabricated hits.
        self.assertEqual(read_corpus("fixture-agent", "is a", base_dir=self._base), [])
        self.assertEqual(read_corpus("fixture-agent", "", base_dir=self._base), [])

    def test_top_n_caps_results(self):
        # A broad term matching every card, capped to 2.
        hits = read_corpus("fixture-agent", "FDA approval CRL accelerated", top_n=2,
                           base_dir=self._base)
        self.assertLessEqual(len(hits), 2)

    def test_malformed_line_skipped_not_fabricated(self):
        d = self._base / "broken-agent"
        d.mkdir(parents=True, exist_ok=True)
        with open(d / "index.jsonl", "w", encoding="utf-8") as f:
            f.write('{"claim":"valid aducanumab card","tier":"T2"}\n')
            f.write("this is not json\n")
            f.write("\n")
        hits = read_corpus("broken-agent", "aducanumab", base_dir=self._base)
        self.assertEqual(len(hits), 1)
        self.assertIn("aducanumab", hits[0]["claim"].lower())

    def test_reads_real_fda_memory_corpus(self):
        # Prove the reader handles the format that actually ships (no fixture).
        if not has_corpus("fda-institutional-memory"):
            self.skipTest("fda-institutional-memory corpus not present")
        hits = read_corpus("fda-institutional-memory",
                           "Is aducanumab accelerated approval for Alzheimer amyloid a viable precedent?",
                           {"drugs": ["aducanumab"], "diseases": ["Alzheimer's disease"]})
        self.assertGreaterEqual(len(hits), 1)
        self.assertTrue(all("source" in h and "tier" in h for h in hits))


if __name__ == "__main__":
    unittest.main()
