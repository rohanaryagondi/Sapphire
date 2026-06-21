"""
test_ingest.py — unit tests for topk_neighbors (Task 3, TDD).

Imports topk_neighbors from _build/build_moat_db.py via importlib/sys.path.
Does NOT import pyarrow or read any parquet file.
"""
import importlib.util
import sys
import unittest
from pathlib import Path

# ── locate _build/build_moat_db.py relative to this file ──────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BUILD_PY = _REPO_ROOT / "_build" / "build_moat_db.py"


def _load_topk_neighbors():
    """Load topk_neighbors without executing main()."""
    spec = importlib.util.spec_from_file_location("build_moat_db", _BUILD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.topk_neighbors


topk_neighbors = _load_topk_neighbors()


# ── shared fixture ─────────────────────────────────────────────────────────────
def _make_rows():
    """
    Small synthetic dataset for query TSC2.

    cosine values: self(TSC2)=0.0, gene_a=0.1, gene_b=0.4, gene_c=0.7, gene_d=0.9
    Expected similar  (k=2): gene_a(rank1), gene_b(rank2)   [smallest cosine ascending]
    Expected opposite (k=2): gene_d(rank1), gene_c(rank2)   [largest  cosine descending]
    The self-row (ref==query, both TSC2) must be EXCLUDED entirely.
    """
    return [
        # self-pair — must be excluded
        {"query": "tsc2",  "query_type": "gene", "ref": "TSC2",   "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.0, "euclidean": 0.0},
        # non-self refs
        {"query": "TSC2",  "query_type": "gene", "ref": "gene_a", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.1, "euclidean": 0.2},
        {"query": "TSC2",  "query_type": "gene", "ref": "gene_b", "ref_type": "compound", "ref_dose": "5",  "cosine": 0.4, "euclidean": 0.5},
        {"query": "TSC2",  "query_type": "gene", "ref": "gene_c", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.7, "euclidean": 0.8},
        {"query": "TSC2",  "query_type": "gene", "ref": "gene_d", "ref_type": "compound", "ref_dose": "10", "cosine": 0.9, "euclidean": 1.0},
        # unrelated query — should not appear in TSC2's results
        {"query": "MTOR",  "query_type": "gene", "ref": "gene_x", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.05, "euclidean": 0.1},
    ]


class TestTopkNeighborsSelfExclusion(unittest.TestCase):
    """Self-pair (ref.upper() == query.upper()) must never appear in output."""

    def test_self_row_excluded(self):
        rows = _make_rows()
        result = topk_neighbors(rows, k=10)
        refs = [r["ref"] for r in result if r["query"] == "TSC2"]
        self.assertNotIn("TSC2", refs, "Self-pair TSC2/TSC2 must be excluded")

    def test_self_row_excluded_case_insensitive(self):
        """Lower-case query with upper-case ref — still a self-pair."""
        rows = [
            {"query": "tsc2", "query_type": "gene", "ref": "TSC2", "ref_type": "gene", "ref_dose": "1", "cosine": 0.0, "euclidean": 0.0},
            {"query": "tsc2", "query_type": "gene", "ref": "gene_a", "ref_type": "gene", "ref_dose": "1", "cosine": 0.3, "euclidean": 0.4},
        ]
        result = topk_neighbors(rows, k=5)
        refs = [r["ref"] for r in result]
        self.assertNotIn("TSC2", refs)
        self.assertIn("gene_a", refs)


class TestTopkNeighborsSimilar(unittest.TestCase):
    """effect='similar': k smallest-cosine, rank ascending 1..k."""

    def setUp(self):
        self.result = topk_neighbors(_make_rows(), k=2)
        self.similar = [r for r in self.result if r["query"] == "TSC2" and r["effect"] == "similar"]
        self.similar_sorted = sorted(self.similar, key=lambda r: r["rank"])

    def test_similar_count(self):
        self.assertEqual(len(self.similar), 2)

    def test_similar_refs(self):
        refs = [r["ref"] for r in self.similar_sorted]
        self.assertEqual(refs, ["gene_a", "gene_b"])

    def test_similar_ranks(self):
        ranks = [r["rank"] for r in self.similar_sorted]
        self.assertEqual(ranks, [1, 2])

    def test_similar_cosine_ascending(self):
        cosines = [r["cosine"] for r in self.similar_sorted]
        self.assertLess(cosines[0], cosines[1])


class TestTopkNeighborsOpposite(unittest.TestCase):
    """effect='opposite': k largest-cosine, rank 1..k descending by cosine."""

    def setUp(self):
        self.result = topk_neighbors(_make_rows(), k=2)
        self.opposite = [r for r in self.result if r["query"] == "TSC2" and r["effect"] == "opposite"]
        self.opposite_sorted = sorted(self.opposite, key=lambda r: r["rank"])

    def test_opposite_count(self):
        self.assertEqual(len(self.opposite), 2)

    def test_opposite_refs(self):
        refs = [r["ref"] for r in self.opposite_sorted]
        self.assertEqual(refs, ["gene_d", "gene_c"])

    def test_opposite_ranks(self):
        ranks = [r["rank"] for r in self.opposite_sorted]
        self.assertEqual(ranks, [1, 2])

    def test_opposite_cosine_descending(self):
        cosines = [r["cosine"] for r in self.opposite_sorted]
        self.assertGreater(cosines[0], cosines[1])


class TestTopkNeighborsUppercase(unittest.TestCase):
    """query field in output must always be UPPERCASE regardless of input case."""

    def test_query_uppercased_mixed_input(self):
        rows = [
            {"query": "tsc2", "query_type": "gene", "ref": "gene_a", "ref_type": "gene", "ref_dose": "1", "cosine": 0.2, "euclidean": 0.3},
        ]
        result = topk_neighbors(rows, k=5)
        for r in result:
            self.assertEqual(r["query"], r["query"].upper(), f"query not uppercased: {r['query']!r}")


class TestTopkNeighborsTiebreak(unittest.TestCase):
    """When cosines are equal, tie-break must be deterministic by ref name ascending."""

    def _run_tiebreak_similar(self):
        rows = [
            {"query": "TSC2", "query_type": "gene", "ref": "zzz", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5},
            {"query": "TSC2", "query_type": "gene", "ref": "aaa", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5},
            {"query": "TSC2", "query_type": "gene", "ref": "mmm", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5},
        ]
        result = topk_neighbors(rows, k=2)
        similar = sorted([r for r in result if r["effect"] == "similar"], key=lambda r: r["rank"])
        return similar

    def test_tiebreak_similar_ascending_ref(self):
        similar = self._run_tiebreak_similar()
        self.assertEqual(len(similar), 2)
        self.assertEqual(similar[0]["ref"], "aaa")
        self.assertEqual(similar[1]["ref"], "mmm")

    def _run_tiebreak_opposite(self):
        rows = [
            {"query": "TSC2", "query_type": "gene", "ref": "zzz", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5},
            {"query": "TSC2", "query_type": "gene", "ref": "aaa", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5},
            {"query": "TSC2", "query_type": "gene", "ref": "mmm", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5},
        ]
        result = topk_neighbors(rows, k=2)
        opposite = sorted([r for r in result if r["effect"] == "opposite"], key=lambda r: r["rank"])
        return opposite

    def test_tiebreak_opposite_ascending_ref(self):
        opposite = self._run_tiebreak_opposite()
        self.assertEqual(len(opposite), 2)
        self.assertEqual(opposite[0]["ref"], "aaa")
        self.assertEqual(opposite[1]["ref"], "mmm")


class TestTopkNeighborsRecordSchema(unittest.TestCase):
    """Each output record must have all required keys."""

    REQUIRED_KEYS = {"query", "query_type", "ref", "ref_type", "ref_dose", "effect", "rank", "cosine", "euclidean"}

    def test_record_has_all_keys(self):
        result = topk_neighbors(_make_rows(), k=2)
        for r in result:
            missing = self.REQUIRED_KEYS - r.keys()
            self.assertEqual(missing, set(), f"Missing keys {missing} in record {r}")


class TestTopkNeighborsIsolation(unittest.TestCase):
    """Results for one query must not bleed into another query's output."""

    def test_mtor_not_in_tsc2_results(self):
        result = topk_neighbors(_make_rows(), k=10)
        tsc2 = [r for r in result if r["query"] == "TSC2"]
        for r in tsc2:
            self.assertNotEqual(r["ref"], "gene_x", "gene_x belongs to MTOR, not TSC2")


class TestTopkNeighborsKBound(unittest.TestCase):
    """Output per (query, effect) must not exceed k."""

    def test_k_bound(self):
        rows = [
            {"query": "TSC2", "query_type": "gene", "ref": f"g{i}", "ref_type": "gene", "ref_dose": "1", "cosine": i * 0.01, "euclidean": i * 0.01}
            for i in range(20)
        ]
        result = topk_neighbors(rows, k=3)
        similar = [r for r in result if r["query"] == "TSC2" and r["effect"] == "similar"]
        opposite = [r for r in result if r["query"] == "TSC2" and r["effect"] == "opposite"]
        self.assertLessEqual(len(similar), 3)
        self.assertLessEqual(len(opposite), 3)


if __name__ == "__main__":
    unittest.main()
