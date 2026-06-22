"""
test_ingest.py — unit tests for topk_neighbors (Task 3, TDD).

Imports topk_neighbors from _build/build_moat_db.py via importlib/sys.path.
Does NOT import pyarrow or read any parquet file.

Direction semantics (verified against real parquet):
  similar  = k smallest-cosine rows where direction == 'Original'
  opposite = k smallest-cosine rows where direction == 'Antipodal'
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
    Small synthetic dataset for query TSC2, with direction column.

    Original rows (similar candidates):
        gene_a cosine=0.1, gene_b cosine=0.4, gene_c cosine=0.7
    Antipodal rows (opposite candidates):
        gene_d cosine=0.2, gene_e cosine=0.5, gene_f cosine=0.8

    Expected with k=2:
        similar  (Original, smallest cosine): gene_a(rank1,0.1), gene_b(rank2,0.4)
        opposite (Antipodal, smallest cosine): gene_d(rank1,0.2), gene_e(rank2,0.5)

    Self-pair (ref==query, both TSC2) must be EXCLUDED entirely.
    Unrelated query MTOR must not bleed into TSC2 results.
    """
    return [
        # self-pair — must be excluded (direction Original)
        {"query": "tsc2",  "query_type": "gene", "ref": "TSC2",   "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.0, "euclidean": 0.0,  "direction": "Original"},
        # Original rows (→ similar)
        {"query": "TSC2",  "query_type": "gene", "ref": "gene_a", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.1, "euclidean": 0.2,  "direction": "Original"},
        {"query": "TSC2",  "query_type": "gene", "ref": "gene_b", "ref_type": "compound", "ref_dose": "5",  "cosine": 0.4, "euclidean": 0.5,  "direction": "Original"},
        {"query": "TSC2",  "query_type": "gene", "ref": "gene_c", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.7, "euclidean": 0.8,  "direction": "Original"},
        # Antipodal rows (→ opposite)
        {"query": "TSC2",  "query_type": "gene", "ref": "gene_d", "ref_type": "compound", "ref_dose": "10", "cosine": 0.2, "euclidean": 0.3,  "direction": "Antipodal"},
        {"query": "TSC2",  "query_type": "gene", "ref": "gene_e", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.5, "euclidean": 0.6,  "direction": "Antipodal"},
        {"query": "TSC2",  "query_type": "gene", "ref": "gene_f", "ref_type": "compound", "ref_dose": "20", "cosine": 0.8, "euclidean": 0.9,  "direction": "Antipodal"},
        # unrelated query — should not appear in TSC2's results
        {"query": "MTOR",  "query_type": "gene", "ref": "gene_x", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.05, "euclidean": 0.1, "direction": "Original"},
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
            {"query": "tsc2", "query_type": "gene", "ref": "TSC2",   "ref_type": "gene", "ref_dose": "1", "cosine": 0.0, "euclidean": 0.0, "direction": "Original"},
            {"query": "tsc2", "query_type": "gene", "ref": "gene_a", "ref_type": "gene", "ref_dose": "1", "cosine": 0.3, "euclidean": 0.4, "direction": "Original"},
        ]
        result = topk_neighbors(rows, k=5)
        refs = [r["ref"] for r in result]
        self.assertNotIn("TSC2", refs)
        self.assertIn("gene_a", refs)


class TestTopkNeighborsSimilar(unittest.TestCase):
    """
    effect='similar': k smallest-cosine Original rows, rank ascending 1..k.
    Must NOT include any Antipodal rows.
    """

    def setUp(self):
        self.result = topk_neighbors(_make_rows(), k=2)
        self.similar = [r for r in self.result if r["query"] == "TSC2" and r["effect"] == "similar"]
        self.similar_sorted = sorted(self.similar, key=lambda r: r["rank"])

    def test_similar_count(self):
        self.assertEqual(len(self.similar), 2)

    def test_similar_refs(self):
        """k=2 smallest Original cosines: gene_a(0.1), gene_b(0.4)."""
        refs = [r["ref"] for r in self.similar_sorted]
        self.assertEqual(refs, ["gene_a", "gene_b"])

    def test_similar_ranks(self):
        ranks = [r["rank"] for r in self.similar_sorted]
        self.assertEqual(ranks, [1, 2])

    def test_similar_cosine_ascending(self):
        cosines = [r["cosine"] for r in self.similar_sorted]
        self.assertLess(cosines[0], cosines[1])

    def test_similar_only_from_original_rows(self):
        """Antipodal ref names (gene_d, gene_e, gene_f) must not appear in similar."""
        antipodal_refs = {"gene_d", "gene_e", "gene_f"}
        similar_refs = {r["ref"] for r in self.similar}
        self.assertTrue(similar_refs.isdisjoint(antipodal_refs),
                        f"Antipodal refs leaked into similar: {similar_refs & antipodal_refs}")


class TestTopkNeighborsOpposite(unittest.TestCase):
    """
    effect='opposite': k smallest-cosine Antipodal rows, rank ascending 1..k.
    Must NOT include any Original rows.
    """

    def setUp(self):
        self.result = topk_neighbors(_make_rows(), k=2)
        self.opposite = [r for r in self.result if r["query"] == "TSC2" and r["effect"] == "opposite"]
        self.opposite_sorted = sorted(self.opposite, key=lambda r: r["rank"])

    def test_opposite_count(self):
        self.assertEqual(len(self.opposite), 2)

    def test_opposite_refs(self):
        """k=2 smallest Antipodal cosines: gene_d(0.2), gene_e(0.5)."""
        refs = [r["ref"] for r in self.opposite_sorted]
        self.assertEqual(refs, ["gene_d", "gene_e"])

    def test_opposite_ranks(self):
        ranks = [r["rank"] for r in self.opposite_sorted]
        self.assertEqual(ranks, [1, 2])

    def test_opposite_cosine_ascending(self):
        cosines = [r["cosine"] for r in self.opposite_sorted]
        self.assertLess(cosines[0], cosines[1])

    def test_opposite_only_from_antipodal_rows(self):
        """Original ref names (gene_a, gene_b, gene_c) must not appear in opposite."""
        original_refs = {"gene_a", "gene_b", "gene_c"}
        opposite_refs = {r["ref"] for r in self.opposite}
        self.assertTrue(opposite_refs.isdisjoint(original_refs),
                        f"Original refs leaked into opposite: {opposite_refs & original_refs}")


class TestTopkNeighborsUppercase(unittest.TestCase):
    """query field in output must always be UPPERCASE regardless of input case."""

    def test_query_uppercased_mixed_input(self):
        rows = [
            {"query": "tsc2", "query_type": "gene", "ref": "gene_a", "ref_type": "gene", "ref_dose": "1", "cosine": 0.2, "euclidean": 0.3, "direction": "Original"},
        ]
        result = topk_neighbors(rows, k=5)
        for r in result:
            self.assertEqual(r["query"], r["query"].upper(), f"query not uppercased: {r['query']!r}")


class TestTopkNeighborsTiebreak(unittest.TestCase):
    """When cosines are equal, tie-break must be deterministic by ref name ascending."""

    def _run_tiebreak_similar(self):
        rows = [
            {"query": "TSC2", "query_type": "gene", "ref": "zzz", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5, "direction": "Original"},
            {"query": "TSC2", "query_type": "gene", "ref": "aaa", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5, "direction": "Original"},
            {"query": "TSC2", "query_type": "gene", "ref": "mmm", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5, "direction": "Original"},
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
            {"query": "TSC2", "query_type": "gene", "ref": "zzz", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5, "direction": "Antipodal"},
            {"query": "TSC2", "query_type": "gene", "ref": "aaa", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5, "direction": "Antipodal"},
            {"query": "TSC2", "query_type": "gene", "ref": "mmm", "ref_type": "gene", "ref_dose": "1", "cosine": 0.5, "euclidean": 0.5, "direction": "Antipodal"},
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
    """Each output record must have all required keys (direction must NOT be in output)."""

    REQUIRED_KEYS = {"query", "query_type", "ref", "ref_type", "ref_dose", "effect", "rank", "cosine", "euclidean"}

    def test_record_has_all_keys(self):
        result = topk_neighbors(_make_rows(), k=2)
        for r in result:
            missing = self.REQUIRED_KEYS - r.keys()
            self.assertEqual(missing, set(), f"Missing keys {missing} in record {r}")

    def test_direction_not_in_output(self):
        result = topk_neighbors(_make_rows(), k=2)
        for r in result:
            self.assertNotIn("direction", r, f"'direction' must not appear in output record: {r}")


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
        rows = (
            [{"query": "TSC2", "query_type": "gene", "ref": f"g{i}", "ref_type": "gene", "ref_dose": "1",
              "cosine": i * 0.01, "euclidean": i * 0.01, "direction": "Original"}
             for i in range(20)]
            +
            [{"query": "TSC2", "query_type": "gene", "ref": f"h{i}", "ref_type": "gene", "ref_dose": "1",
              "cosine": i * 0.01, "euclidean": i * 0.01, "direction": "Antipodal"}
             for i in range(20)]
        )
        result = topk_neighbors(rows, k=3)
        similar = [r for r in result if r["query"] == "TSC2" and r["effect"] == "similar"]
        opposite = [r for r in result if r["query"] == "TSC2" and r["effect"] == "opposite"]
        self.assertLessEqual(len(similar), 3)
        self.assertLessEqual(len(opposite), 3)


class TestTopkNeighborsMissingDirection(unittest.TestCase):
    """Rows without a direction key should default to 'Original' (similar)."""

    def test_no_direction_defaults_to_original(self):
        rows = [
            {"query": "TSC2", "query_type": "gene", "ref": "gene_a", "ref_type": "gene", "ref_dose": "1",
             "cosine": 0.3, "euclidean": 0.4},
        ]
        result = topk_neighbors(rows, k=5)
        similar = [r for r in result if r["effect"] == "similar"]
        self.assertEqual(len(similar), 1)
        self.assertEqual(similar[0]["ref"], "gene_a")


if __name__ == "__main__":
    unittest.main()
