"""
test_ingest.py — unit tests for topk_neighbors (WO-5 dual-rank fix).

Imports topk_neighbors from _build/build_moat_db.py via importlib/sys.path.
Does NOT import pyarrow or read any parquet file.

Direction semantics (verified against real parquet):
  similar  = k smallest-cosine rows where direction == 'Original'
  opposite = k smallest-cosine rows where direction == 'Antipodal'

Dual-rank union: a candidate survives if rank_cosine <= k OR rank_euclidean <= k.
Output carries rank_cosine, rank_euclidean, union_rank (not 'rank').

Partitioning: per (query, effect, ref_type) — genes and compounds each get
their own top-K list; ranks restart at 1 within each group.
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

    Original rows (similar candidates) — mixed ref_types:
        gene_a cosine=0.1  ref_type=gene
        gene_b cosine=0.4  ref_type=compound
        gene_c cosine=0.7  ref_type=gene
    Antipodal rows (opposite candidates) — mixed ref_types:
        gene_d cosine=0.2  ref_type=compound
        gene_e cosine=0.5  ref_type=gene
        gene_f cosine=0.8  ref_type=compound

    With k=2, per-(query, effect, ref_type) partitioning:
        similar-gene:     gene_a(rank_cos=1), gene_c(rank_cos=2)
        similar-compound: gene_b(rank_cos=1)
        opposite-compound: gene_d(rank_cos=1), gene_f(rank_cos=2)
        opposite-gene:    gene_e(rank_cos=1)

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
    effect='similar': k smallest-cosine Original rows per ref_type, rank_cosine 1..k within each group.
    Must NOT include any Antipodal rows.
    Grouping is per (query, effect, ref_type): genes and compounds each get their own ranked list.
    """

    def setUp(self):
        self.result = topk_neighbors(_make_rows(), k=2)
        self.similar = [r for r in self.result if r["query"] == "TSC2" and r["effect"] == "similar"]

    def test_similar_count(self):
        # similar-gene: gene_a, gene_c = 2 rows
        # similar-compound: gene_b = 1 row
        # total = 3
        self.assertEqual(len(self.similar), 3)

    def test_similar_gene_refs(self):
        """k=2 smallest Original cosines for ref_type=gene: gene_a(0.1), gene_c(0.7)."""
        sim_gene = sorted(
            [r for r in self.similar if r["ref_type"] == "gene"],
            key=lambda r: r["union_rank"]
        )
        refs = [r["ref"] for r in sim_gene]
        self.assertEqual(refs, ["gene_a", "gene_c"])

    def test_similar_gene_ranks_restart(self):
        """rank_cosine within similar-gene restarts at 1."""
        sim_gene = sorted(
            [r for r in self.similar if r["ref_type"] == "gene"],
            key=lambda r: r["union_rank"]
        )
        ranks = [r["rank_cosine"] for r in sim_gene]
        self.assertEqual(ranks, [1, 2])

    def test_similar_compound_refs(self):
        """k=2 smallest Original cosines for ref_type=compound: gene_b(0.4) only 1 row."""
        sim_cpd = sorted(
            [r for r in self.similar if r["ref_type"] == "compound"],
            key=lambda r: r["union_rank"]
        )
        refs = [r["ref"] for r in sim_cpd]
        self.assertEqual(refs, ["gene_b"])

    def test_similar_compound_rank_starts_at_1(self):
        """similar-compound rank_cosine starts at 1 independently of similar-gene."""
        sim_cpd = [r for r in self.similar if r["ref_type"] == "compound"]
        self.assertEqual(len(sim_cpd), 1)
        self.assertEqual(sim_cpd[0]["rank_cosine"], 1)

    def test_similar_only_from_original_rows(self):
        """Antipodal ref names (gene_d, gene_e, gene_f) must not appear in similar."""
        antipodal_refs = {"gene_d", "gene_e", "gene_f"}
        similar_refs = {r["ref"] for r in self.similar}
        self.assertTrue(similar_refs.isdisjoint(antipodal_refs),
                        f"Antipodal refs leaked into similar: {similar_refs & antipodal_refs}")


class TestTopkNeighborsOpposite(unittest.TestCase):
    """
    effect='opposite': k smallest-cosine Antipodal rows per ref_type, rank_cosine 1..k within each group.
    Must NOT include any Original rows.
    Grouping is per (query, effect, ref_type): genes and compounds each get their own ranked list.
    """

    def setUp(self):
        self.result = topk_neighbors(_make_rows(), k=2)
        self.opposite = [r for r in self.result if r["query"] == "TSC2" and r["effect"] == "opposite"]

    def test_opposite_count(self):
        # opposite-compound: gene_d(0.2), gene_f(0.8) = 2 rows
        # opposite-gene:    gene_e(0.5) = 1 row
        # total = 3
        self.assertEqual(len(self.opposite), 3)

    def test_opposite_compound_refs(self):
        """k=2 smallest Antipodal cosines for ref_type=compound: gene_d(0.2), gene_f(0.8)."""
        opp_cpd = sorted(
            [r for r in self.opposite if r["ref_type"] == "compound"],
            key=lambda r: r["union_rank"]
        )
        refs = [r["ref"] for r in opp_cpd]
        self.assertEqual(refs, ["gene_d", "gene_f"])

    def test_opposite_compound_ranks_restart(self):
        """rank_cosine within opposite-compound restarts at 1."""
        opp_cpd = sorted(
            [r for r in self.opposite if r["ref_type"] == "compound"],
            key=lambda r: r["union_rank"]
        )
        ranks = [r["rank_cosine"] for r in opp_cpd]
        self.assertEqual(ranks, [1, 2])

    def test_opposite_gene_refs(self):
        """k=2 smallest Antipodal cosines for ref_type=gene: gene_e(0.5) only 1 row."""
        opp_gene = sorted(
            [r for r in self.opposite if r["ref_type"] == "gene"],
            key=lambda r: r["union_rank"]
        )
        refs = [r["ref"] for r in opp_gene]
        self.assertEqual(refs, ["gene_e"])

    def test_opposite_gene_rank_starts_at_1(self):
        """opposite-gene rank_cosine starts at 1 independently of opposite-compound."""
        opp_gene = [r for r in self.opposite if r["ref_type"] == "gene"]
        self.assertEqual(len(opp_gene), 1)
        self.assertEqual(opp_gene[0]["rank_cosine"], 1)

    def test_opposite_compound_cosine_ascending(self):
        """Within opposite-compound, cosines are ascending by union_rank."""
        opp_cpd = sorted(
            [r for r in self.opposite if r["ref_type"] == "compound"],
            key=lambda r: r["union_rank"]
        )
        cosines = [r["cosine"] for r in opp_cpd]
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
        similar = sorted([r for r in result if r["effect"] == "similar"], key=lambda r: r["union_rank"])
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
        opposite = sorted([r for r in result if r["effect"] == "opposite"], key=lambda r: r["union_rank"])
        return opposite

    def test_tiebreak_opposite_ascending_ref(self):
        opposite = self._run_tiebreak_opposite()
        self.assertEqual(len(opposite), 2)
        self.assertEqual(opposite[0]["ref"], "aaa")
        self.assertEqual(opposite[1]["ref"], "mmm")


class TestTopkNeighborsRecordSchema(unittest.TestCase):
    """Each output record must have all required keys (direction must NOT be in output)."""

    REQUIRED_KEYS = {
        "query", "query_type", "ref", "ref_type", "ref_dose",
        "effect", "rank_cosine", "rank_euclidean", "union_rank",
        "cosine", "euclidean",
    }

    def test_record_has_all_keys(self):
        result = topk_neighbors(_make_rows(), k=2)
        for r in result:
            missing = self.REQUIRED_KEYS - r.keys()
            self.assertEqual(missing, set(), f"Missing keys {missing} in record {r}")

    def test_direction_not_in_output(self):
        result = topk_neighbors(_make_rows(), k=2)
        for r in result:
            self.assertNotIn("direction", r, f"'direction' must not appear in output record: {r}")

    def test_rank_not_in_output(self):
        """Old single 'rank' field must not appear — replaced by rank_cosine/rank_euclidean/union_rank."""
        result = topk_neighbors(_make_rows(), k=2)
        for r in result:
            self.assertNotIn("rank", r, f"Old 'rank' field must not appear in output: {r}")


class TestTopkNeighborsIsolation(unittest.TestCase):
    """Results for one query must not bleed into another query's output."""

    def test_mtor_not_in_tsc2_results(self):
        result = topk_neighbors(_make_rows(), k=10)
        tsc2 = [r for r in result if r["query"] == "TSC2"]
        for r in tsc2:
            self.assertNotEqual(r["ref"], "gene_x", "gene_x belongs to MTOR, not TSC2")


class TestTopkNeighborsPerRefType(unittest.TestCase):
    """
    Per-(query, effect, ref_type) partitioning: genes and compounds must each get their own
    top-K ranked list. rank_cosine restarts at 1 within each (query, effect, ref_type) group.
    A query with both gene and compound refs in both directions must produce four separate
    ranked groups: similar-gene, similar-compound, opposite-gene, opposite-compound.
    """

    def _make_mixed_rows(self):
        """
        Query BRCA1 with 3 gene + 3 compound refs in each direction.
        similar-gene candidates (Original, ref_type=gene):
            gA cosine=0.1, gB cosine=0.3, gC cosine=0.5
        similar-compound candidates (Original, ref_type=compound):
            cA cosine=0.2, cB cosine=0.4, cC cosine=0.6
        opposite-gene candidates (Antipodal, ref_type=gene):
            gD cosine=0.15, gE cosine=0.35, gF cosine=0.55
        opposite-compound candidates (Antipodal, ref_type=compound):
            cD cosine=0.25, cE cosine=0.45, cF cosine=0.65
        """
        return [
            # similar-gene
            {"query": "BRCA1", "query_type": "gene", "ref": "gA", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.1,  "euclidean": 0.1, "direction": "Original"},
            {"query": "BRCA1", "query_type": "gene", "ref": "gB", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.3,  "euclidean": 0.3, "direction": "Original"},
            {"query": "BRCA1", "query_type": "gene", "ref": "gC", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.5,  "euclidean": 0.5, "direction": "Original"},
            # similar-compound
            {"query": "BRCA1", "query_type": "gene", "ref": "cA", "ref_type": "compound", "ref_dose": "5",  "cosine": 0.2,  "euclidean": 0.2, "direction": "Original"},
            {"query": "BRCA1", "query_type": "gene", "ref": "cB", "ref_type": "compound", "ref_dose": "5",  "cosine": 0.4,  "euclidean": 0.4, "direction": "Original"},
            {"query": "BRCA1", "query_type": "gene", "ref": "cC", "ref_type": "compound", "ref_dose": "5",  "cosine": 0.6,  "euclidean": 0.6, "direction": "Original"},
            # opposite-gene
            {"query": "BRCA1", "query_type": "gene", "ref": "gD", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.15, "euclidean": 0.15, "direction": "Antipodal"},
            {"query": "BRCA1", "query_type": "gene", "ref": "gE", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.35, "euclidean": 0.35, "direction": "Antipodal"},
            {"query": "BRCA1", "query_type": "gene", "ref": "gF", "ref_type": "gene",     "ref_dose": "1",  "cosine": 0.55, "euclidean": 0.55, "direction": "Antipodal"},
            # opposite-compound
            {"query": "BRCA1", "query_type": "gene", "ref": "cD", "ref_type": "compound", "ref_dose": "10", "cosine": 0.25, "euclidean": 0.25, "direction": "Antipodal"},
            {"query": "BRCA1", "query_type": "gene", "ref": "cE", "ref_type": "compound", "ref_dose": "10", "cosine": 0.45, "euclidean": 0.45, "direction": "Antipodal"},
            {"query": "BRCA1", "query_type": "gene", "ref": "cF", "ref_type": "compound", "ref_dose": "10", "cosine": 0.65, "euclidean": 0.65, "direction": "Antipodal"},
        ]

    def setUp(self):
        self.rows = self._make_mixed_rows()
        self.result = topk_neighbors(self.rows, k=2)
        self.brca1 = [r for r in self.result if r["query"] == "BRCA1"]

    def test_four_groups_present(self):
        """All four (effect, ref_type) groups must appear: similar-gene, similar-compound, opposite-gene, opposite-compound."""
        groups = {(r["effect"], r["ref_type"]) for r in self.brca1}
        self.assertIn(("similar",  "gene"),     groups)
        self.assertIn(("similar",  "compound"), groups)
        self.assertIn(("opposite", "gene"),     groups)
        self.assertIn(("opposite", "compound"), groups)

    def test_similar_gene_top2(self):
        sim_gene = sorted([r for r in self.brca1 if r["effect"] == "similar" and r["ref_type"] == "gene"], key=lambda r: r["union_rank"])
        self.assertEqual([r["ref"] for r in sim_gene], ["gA", "gB"])
        self.assertEqual([r["rank_cosine"] for r in sim_gene], [1, 2])

    def test_similar_compound_top2(self):
        sim_cpd = sorted([r for r in self.brca1 if r["effect"] == "similar" and r["ref_type"] == "compound"], key=lambda r: r["union_rank"])
        self.assertEqual([r["ref"] for r in sim_cpd], ["cA", "cB"])
        self.assertEqual([r["rank_cosine"] for r in sim_cpd], [1, 2])

    def test_opposite_gene_top2(self):
        opp_gene = sorted([r for r in self.brca1 if r["effect"] == "opposite" and r["ref_type"] == "gene"], key=lambda r: r["union_rank"])
        self.assertEqual([r["ref"] for r in opp_gene], ["gD", "gE"])
        self.assertEqual([r["rank_cosine"] for r in opp_gene], [1, 2])

    def test_opposite_compound_top2(self):
        opp_cpd = sorted([r for r in self.brca1 if r["effect"] == "opposite" and r["ref_type"] == "compound"], key=lambda r: r["union_rank"])
        self.assertEqual([r["ref"] for r in opp_cpd], ["cD", "cE"])
        self.assertEqual([r["rank_cosine"] for r in opp_cpd], [1, 2])

    def test_ranks_restart_per_ref_type(self):
        """rank_cosine=1 must appear exactly once per (effect, ref_type) group."""
        for effect in ("similar", "opposite"):
            for ref_type in ("gene", "compound"):
                group = [r for r in self.brca1 if r["effect"] == effect and r["ref_type"] == ref_type]
                rank1_count = sum(1 for r in group if r["rank_cosine"] == 1)
                self.assertEqual(rank1_count, 1, f"Expected exactly one rank_cosine=1 in ({effect}, {ref_type}) group")

    def test_compounds_not_crowded_out_by_genes(self):
        """With k=2, compounds must appear even alongside genes — compound group is independent."""
        sim_cpd = [r for r in self.brca1 if r["effect"] == "similar" and r["ref_type"] == "compound"]
        self.assertEqual(len(sim_cpd), 2, "Compounds must not be crowded out by genes — per-ref_type partitioning must give compounds their own k=2 slots")

    def test_self_excluded_across_all_groups(self):
        """Self-pairs must be excluded in all (effect, ref_type) groups."""
        refs = {r["ref"] for r in self.brca1}
        self.assertNotIn("BRCA1", refs)


class TestTopkNeighborsKBound(unittest.TestCase):
    """Output per (query, effect, ref_type) must not exceed k (when cosine == euclidean)."""

    def test_k_bound(self):
        # 20 gene refs in each direction — only ref_type=gene; each group capped at k=3
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
        # With cosine == euclidean, the top-3 by cosine == top-3 by euclidean.
        # Union size = 3 (not 2k).
        similar_gene = [r for r in result if r["query"] == "TSC2" and r["effect"] == "similar" and r["ref_type"] == "gene"]
        opposite_gene = [r for r in result if r["query"] == "TSC2" and r["effect"] == "opposite" and r["ref_type"] == "gene"]
        self.assertLessEqual(len(similar_gene), 3)
        self.assertLessEqual(len(opposite_gene), 3)

    def test_k_bound_per_ref_type_independent(self):
        """Each (effect, ref_type) group gets its own k-capped list; both gene and compound can each have up to k rows."""
        rows = (
            [{"query": "TSC2", "query_type": "gene", "ref": f"g{i}", "ref_type": "gene",     "ref_dose": "1",
              "cosine": i * 0.01, "euclidean": i * 0.01, "direction": "Original"}
             for i in range(10)]
            +
            [{"query": "TSC2", "query_type": "gene", "ref": f"c{i}", "ref_type": "compound", "ref_dose": "5",
              "cosine": i * 0.01, "euclidean": i * 0.01, "direction": "Original"}
             for i in range(10)]
        )
        result = topk_neighbors(rows, k=3)
        similar_gene = [r for r in result if r["query"] == "TSC2" and r["effect"] == "similar" and r["ref_type"] == "gene"]
        similar_cpd  = [r for r in result if r["query"] == "TSC2" and r["effect"] == "similar" and r["ref_type"] == "compound"]
        # Each ref_type group independently capped at k=3
        self.assertEqual(len(similar_gene), 3)
        self.assertEqual(len(similar_cpd),  3)


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


class TestTopkNeighborsHeapUnionFix(unittest.TestCase):
    """
    The dual-rank union fix: a row that is euclidean-top-K but NOT cosine-top-K must survive.

    Scenario: k=2, three refs where:
        ref_A: cosine=0.1, euclidean=0.9  → rank_cosine=1, rank_euclidean=k+1=3 (not in euc top-2)
        ref_B: cosine=0.2, euclidean=0.8  → rank_cosine=2, rank_euclidean=2
        ref_C: cosine=0.9, euclidean=0.1  → rank_cosine=k+1=3, rank_euclidean=1

    With k=2:
        cosine top-2:    ref_A(cos=0.1), ref_B(cos=0.2)  → rank_cosine: A=1, B=2
        euclidean top-2: ref_C(euc=0.1), ref_B(euc=0.8)  → rank_euclidean: C=1, B=2

    Union = {ref_A, ref_B, ref_C} — all three survive!
        ref_A: rank_cosine=1, rank_euclidean=k+1=3, union_rank=4
        ref_B: rank_cosine=2, rank_euclidean=2,     union_rank=4
        ref_C: rank_cosine=k+1=3, rank_euclidean=1, union_rank=4

    Critical assertion: ref_C (euclidean-best but cosine-worst) MUST be in output.
    """

    def _make_dual_rank_rows(self, direction="Antipodal"):
        return [
            {"query": "TSC2", "query_type": "gene", "ref": "ref_A",
             "ref_type": "gene", "ref_dose": "1",
             "cosine": 0.1, "euclidean": 0.9, "direction": direction},
            {"query": "TSC2", "query_type": "gene", "ref": "ref_B",
             "ref_type": "gene", "ref_dose": "1",
             "cosine": 0.2, "euclidean": 0.8, "direction": direction},
            {"query": "TSC2", "query_type": "gene", "ref": "ref_C",
             "ref_type": "gene", "ref_dose": "1",
             "cosine": 0.9, "euclidean": 0.1, "direction": direction},
        ]

    def test_euclidean_top_k_not_cosine_top_k_survives(self):
        rows = self._make_dual_rank_rows("Antipodal")
        result = topk_neighbors(rows, k=2)
        opposite = [r for r in result if r["effect"] == "opposite"]
        refs_in_output = {r["ref"] for r in opposite}
        # All three must survive — ref_C is euclidean-top-1 but cosine-rank=3>k=2
        self.assertIn("ref_C", refs_in_output,
                      "ref_C is euclidean-top-1 but cosine-rank=3>k=2; "
                      "dual-rank union fix must keep it")
        self.assertIn("ref_A", refs_in_output)
        self.assertIn("ref_B", refs_in_output)

    def test_euclidean_top_k_has_correct_rank_euclidean(self):
        rows = self._make_dual_rank_rows("Antipodal")
        result = topk_neighbors(rows, k=2)
        opposite = [r for r in result if r["effect"] == "opposite"]
        ref_c = next((r for r in opposite if r["ref"] == "ref_C"), None)
        self.assertIsNotNone(ref_c, "ref_C must be in output")
        self.assertEqual(ref_c["rank_euclidean"], 1,
                         "ref_C is euclidean-rank=1 globally, must be stored as 1")
        # ref_C's cosine rank is 3 (>k=2), so sentinel = k+1 = 3
        self.assertEqual(ref_c["rank_cosine"], 3,
                         "ref_C cosine-rank=3 > k=2, sentinel k+1=3 expected")

    def test_cosine_top_k_only_candidate_has_sentinel_euc_rank(self):
        """ref_A is in cosine top-2 but NOT euclidean top-2; must get rank_euclidean=k+1."""
        rows = self._make_dual_rank_rows("Antipodal")
        result = topk_neighbors(rows, k=2)
        opposite = [r for r in result if r["effect"] == "opposite"]
        ref_a = next((r for r in opposite if r["ref"] == "ref_A"), None)
        self.assertIsNotNone(ref_a, "ref_A must be in output")
        self.assertEqual(ref_a["rank_cosine"], 1)
        self.assertEqual(ref_a["rank_euclidean"], 3,  # sentinel = k+1 = 3
                         "ref_A is not in euclidean top-2; sentinel k+1=3 expected")

    def test_union_rank_ordering(self):
        """Output must be ordered by union_rank ASC (then ref for tiebreak)."""
        rows = [
            # ref_X: cosine=0.3, euclidean=0.5 → rank_cos=2, rank_euc=2 → union=4
            {"query": "TSC2", "query_type": "gene", "ref": "ref_X",
             "ref_type": "gene", "ref_dose": "1",
             "cosine": 0.3, "euclidean": 0.5, "direction": "Original"},
            # ref_Y: cosine=0.1, euclidean=0.9 → rank_cos=1, rank_euc=k+1=3 → union=4
            {"query": "TSC2", "query_type": "gene", "ref": "ref_Y",
             "ref_type": "gene", "ref_dose": "1",
             "cosine": 0.1, "euclidean": 0.9, "direction": "Original"},
            # ref_Z: cosine=0.8, euclidean=0.1 → rank_cos=k+1=3, rank_euc=1 → union=4
            {"query": "TSC2", "query_type": "gene", "ref": "ref_Z",
             "ref_type": "gene", "ref_dose": "1",
             "cosine": 0.8, "euclidean": 0.1, "direction": "Original"},
        ]
        result = topk_neighbors(rows, k=2)
        similar = [r for r in result if r["effect"] == "similar"]
        # Verify output is sorted by union_rank ascending
        union_ranks = [r["union_rank"] for r in similar]
        self.assertEqual(union_ranks, sorted(union_ranks),
                         f"Output not sorted by union_rank: {union_ranks}")

    def test_similar_direction_also_uses_dual_rank(self):
        """Dual-rank fix applies to Original (similar) direction too."""
        rows = self._make_dual_rank_rows("Original")
        result = topk_neighbors(rows, k=2)
        similar = [r for r in result if r["effect"] == "similar"]
        refs_in_output = {r["ref"] for r in similar}
        self.assertIn("ref_C", refs_in_output,
                      "ref_C must survive in similar via dual-rank union")
        self.assertIn("ref_A", refs_in_output)
        self.assertIn("ref_B", refs_in_output)

    def test_union_rank_value_correct(self):
        """union_rank == rank_cosine + rank_euclidean for every record."""
        rows = self._make_dual_rank_rows("Antipodal")
        result = topk_neighbors(rows, k=2)
        for r in result:
            self.assertEqual(
                r["union_rank"], r["rank_cosine"] + r["rank_euclidean"],
                f"union_rank mismatch for {r['ref']}: "
                f"{r['union_rank']} != {r['rank_cosine']} + {r['rank_euclidean']}"
            )


if __name__ == "__main__":
    unittest.main()
