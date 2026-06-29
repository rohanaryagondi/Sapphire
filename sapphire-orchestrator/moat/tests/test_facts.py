"""
Tests for moat_facts (Task 4, updated for WO-5 dual-rank schema).

Builds a temp SQLite fixture with TSC2 rows (11-column dual-rank schema),
then asserts dossier-shaped fact rows are returned with provenance="moat-real".
All stdlib — no pyarrow, no pandas.

Schema change (WO-5): 'rank' column replaced by rank_cosine, rank_euclidean,
union_rank. Facts now also include 'supporting_genes' field.
"""
import os
import sqlite3
import tempfile
import unittest


def _make_fixture_db() -> str:
    """Create a temp SQLite DB with TSC2 neighbor rows; return file path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    db_path = tmp.name
    tmp.close()

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE neighbors (
            query          TEXT,
            query_type     TEXT,
            ref            TEXT,
            ref_type       TEXT,
            ref_dose       TEXT,
            effect         TEXT,
            rank_cosine    INTEGER,
            rank_euclidean INTEGER,
            union_rank     INTEGER,
            cosine         REAL,
            euclidean      REAL
        )
    """)
    cur.execute("""
        CREATE TABLE moat_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    # Tuple: (query, query_type, ref, ref_type, ref_dose, effect,
    #         rank_cosine, rank_euclidean, union_rank, cosine, euclidean)
    rows = [
        # similar genes (EP-signature mimics) — distinct union_ranks
        ("TSC2", "gene", "TSC1",  "gene",     None,   "similar",  1, 2, 3, 0.97,  0.18),
        ("TSC2", "gene", "RHEB",  "gene",     None,   "similar",  2, 3, 5, 0.89,  0.31),
        # rescue GENES (opposite EP-signature genes) — the rescuers, union_rank-ordered
        ("TSC2", "gene", "DCTN6", "gene",     None,   "opposite", 1, 1, 2, 0.163, 0.50),
        ("TSC2", "gene", "FZD7",  "gene",     None,   "opposite", 2, 2, 4, 0.204, 0.55),
        # rescue compound (opposite EP-signature compound)
        ("TSC2", "gene", "RAPAMYCIN", "compound", "10nM", "opposite", 1, 1, 2, 0.823, 0.44),
    ]
    cur.executemany("INSERT INTO neighbors VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    cur.execute("INSERT INTO moat_meta VALUES ('version','test-1.0')")
    con.commit()
    con.close()
    return db_path


class TestMoatFactsHappyPath(unittest.TestCase):

    def setUp(self):
        self._db_path = _make_fixture_db()
        from moat.client import MoatClient
        from moat.facts import moat_facts
        self.client = MoatClient(db_path=self._db_path)
        self.moat_facts = moat_facts

    def tearDown(self):
        os.unlink(self._db_path)

    def test_returns_list(self):
        facts = self.moat_facts("TSC2", client=self.client)
        self.assertIsInstance(facts, list)

    def test_all_provenance_moat_real(self):
        facts = self.moat_facts("TSC2", client=self.client)
        self.assertGreater(len(facts), 0)
        for f in facts:
            self.assertEqual(f["provenance"], "moat-real")

    def test_all_tier_T2(self):
        facts = self.moat_facts("TSC2", client=self.client)
        for f in facts:
            self.assertEqual(f["tier"], "T2")

    def test_all_source_quiver_moat(self):
        facts = self.moat_facts("TSC2", client=self.client)
        for f in facts:
            self.assertEqual(f["source"], "Quiver moat (CNS_DFP, real)")

    def test_includes_similar_gene_row(self):
        facts = self.moat_facts("TSC2", client=self.client)
        gene_rows = [f for f in facts if f["field"] == "moat similar (gene)"]
        self.assertGreater(len(gene_rows), 0, "expected at least one similar-gene fact")
        refs = [f["value"] for f in gene_rows]
        self.assertTrue(any("TSC1" in v for v in refs), f"TSC1 not found in {refs}")

    def test_includes_rescue_compound_row(self):
        facts = self.moat_facts("TSC2", client=self.client)
        cpd_rows = [f for f in facts if f["field"] == "moat rescue (compound)"]
        self.assertGreater(len(cpd_rows), 0, "expected at least one rescue-compound fact")
        refs = [f["value"] for f in cpd_rows]
        self.assertTrue(any("RAPAMYCIN" in v for v in refs), f"RAPAMYCIN not found in {refs}")

    def test_gene_row_value_format(self):
        facts = self.moat_facts("TSC2", client=self.client)
        gene_rows = [f for f in facts if f["field"] == "moat similar (gene)"]
        # Value should start with "EP-signature mimic:"
        for f in gene_rows:
            self.assertTrue(
                f["value"].startswith("EP-signature mimic:"),
                f"Unexpected gene fact value: {f['value']}"
            )

    def test_compound_row_value_format(self):
        facts = self.moat_facts("TSC2", client=self.client)
        cpd_rows = [f for f in facts if f["field"] == "moat rescue (compound)"]
        for f in cpd_rows:
            self.assertTrue(
                f["value"].startswith("Rescue candidate:"),
                f"Unexpected compound fact value: {f['value']}"
            )

    def test_cosine_rounded_to_3_decimals_in_value(self):
        facts = self.moat_facts("TSC2", client=self.client)
        # RAPAMYCIN has cosine=0.823
        cpd_rows = [f for f in facts if f["field"] == "moat rescue (compound)"]
        self.assertTrue(any("0.823" in f["value"] for f in cpd_rows))

    def test_similar_genes_come_before_compounds(self):
        """Similar-gene rows must come before rescue-compound rows.
        (Rescue-gene rows may appear in between — that's fine.)
        """
        facts = self.moat_facts("TSC2", client=self.client)
        gene_indices = [i for i, f in enumerate(facts) if f["field"] == "moat similar (gene)"]
        cpd_indices  = [i for i, f in enumerate(facts) if f["field"] == "moat rescue (compound)"]
        if gene_indices and cpd_indices:
            self.assertLess(max(gene_indices), min(cpd_indices))

    def test_fact_has_required_keys(self):
        facts = self.moat_facts("TSC2", client=self.client)
        required = {"field", "value", "source", "tier", "provenance", "supporting_genes"}
        for f in facts:
            self.assertTrue(required.issubset(f.keys()), f"Missing keys in {f}")

    def test_k_limits_results(self):
        facts = self.moat_facts("TSC2", client=self.client, k=1)
        gene_rows = [f for f in facts if f["field"] == "moat similar (gene)"]
        cpd_rows  = [f for f in facts if f["field"] == "moat rescue (compound)"]
        self.assertLessEqual(len(gene_rows), 1)
        self.assertLessEqual(len(cpd_rows), 1)

    def test_case_insensitive_perturbation(self):
        facts_lower = self.moat_facts("tsc2", client=self.client)
        facts_upper = self.moat_facts("TSC2", client=self.client)
        self.assertEqual(len(facts_lower), len(facts_upper))

    def test_includes_rescue_gene_row(self):
        facts = self.moat_facts("TSC2", client=self.client)
        gene_rows = [f for f in facts if f["field"] == "moat rescue (gene)"]
        self.assertGreater(len(gene_rows), 0, "expected at least one rescue-gene fact")
        refs = [f["value"] for f in gene_rows]
        self.assertTrue(any("DCTN6" in v for v in refs), f"DCTN6 not found in {refs}")

    def test_rescue_gene_row_value_format(self):
        facts = self.moat_facts("TSC2", client=self.client)
        gene_rows = [f for f in facts if f["field"] == "moat rescue (gene)"]
        for f in gene_rows:
            self.assertTrue(
                f["value"].startswith("Rescue gene:"),
                f"Unexpected rescue-gene fact value: {f['value']}"
            )

    def test_rescue_gene_value_includes_union_rank(self):
        """Rescue-gene value strings must include the union_rank field."""
        facts = self.moat_facts("TSC2", client=self.client)
        rescue_gene_rows = [f for f in facts if f["field"] == "moat rescue (gene)"]
        self.assertGreater(len(rescue_gene_rows), 0)
        for f in rescue_gene_rows:
            self.assertIn("union_rank", f["value"],
                          f"union_rank not in rescue-gene value: {f['value']}")

    def test_rescue_genes_distinct_from_similar_genes(self):
        # The rescuers (opposite genes) must NOT be confused with the similar genes.
        facts = self.moat_facts("TSC2", client=self.client)
        rescue = {f["value"] for f in facts if f["field"] == "moat rescue (gene)"}
        similar = {f["value"] for f in facts if f["field"] == "moat similar (gene)"}
        self.assertTrue(any("DCTN6" in v for v in rescue))
        self.assertFalse(any("DCTN6" in v for v in similar))
        self.assertTrue(any("TSC1" in v for v in similar))
        self.assertFalse(any("TSC1" in v for v in rescue))

    def test_supporting_genes_present(self):
        """Every fact must carry supporting_genes (int >= 1)."""
        facts = self.moat_facts("TSC2", client=self.client)
        self.assertGreater(len(facts), 0)
        for f in facts:
            self.assertIn("supporting_genes", f,
                          f"supporting_genes missing from fact: {f}")
            self.assertIsInstance(f["supporting_genes"], int)
            self.assertGreaterEqual(f["supporting_genes"], 1)

    def test_supporting_genes_present_all_categories(self):
        """supporting_genes must be present in similar-gene, rescue-gene, AND rescue-compound."""
        facts = self.moat_facts("TSC2", client=self.client)
        for field in ("moat similar (gene)", "moat rescue (gene)", "moat rescue (compound)"):
            category_facts = [f for f in facts if f["field"] == field]
            for f in category_facts:
                self.assertIn(
                    "supporting_genes", f,
                    f"supporting_genes missing from {field} fact: {f}"
                )


class TestRescueGenes(unittest.TestCase):
    """Structured rescue_genes() feed (the ranked-synthesis input)."""

    def setUp(self):
        self._db_path = _make_fixture_db()
        from moat.client import MoatClient
        from moat.facts import rescue_genes
        self.client = MoatClient(db_path=self._db_path)
        self.rescue_genes = rescue_genes

    def tearDown(self):
        os.unlink(self._db_path)

    def test_returns_opposite_genes_only(self):
        rows = self.rescue_genes("TSC2", client=self.client)
        self.assertGreater(len(rows), 0)
        genes = [r["gene"] for r in rows]
        self.assertIn("DCTN6", genes)
        self.assertIn("FZD7", genes)
        # similar genes and compounds must NOT appear
        self.assertNotIn("TSC1", genes)
        self.assertNotIn("RAPAMYCIN", genes)

    def test_rank_ordered_best_first(self):
        """rescue_genes() returns rows ordered by union_rank (rank field = union_rank)."""
        rows = self.rescue_genes("TSC2", client=self.client)
        ranks = [r["rank"] for r in rows]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(rows[0]["gene"], "DCTN6")  # lowest union_rank

    def test_structured_keys(self):
        rows = self.rescue_genes("TSC2", client=self.client)
        required = {"rank", "gene", "cosine", "euclidean", "perturbation",
                    "source", "tier", "provenance"}
        for r in rows:
            self.assertTrue(required.issubset(r.keys()), f"missing keys in {r}")
            self.assertEqual(r["provenance"], "moat-real")
            self.assertEqual(r["perturbation"], "TSC2")

    def test_cosine_rounded(self):
        rows = self.rescue_genes("TSC2", client=self.client)
        self.assertAlmostEqual(rows[0]["cosine"], 0.163, places=3)

    def test_k_limits(self):
        rows = self.rescue_genes("TSC2", client=self.client, k=1)
        self.assertEqual(len(rows), 1)

    def test_case_insensitive(self):
        self.assertEqual(
            len(self.rescue_genes("tsc2", client=self.client)),
            len(self.rescue_genes("TSC2", client=self.client)),
        )

    def test_unavailable_client_returns_empty(self):
        from moat.client import MoatClient
        from moat.facts import rescue_genes
        bad = MoatClient(db_path="/tmp/__no_such_moat_rescue_genes__.sqlite")
        self.assertEqual(rescue_genes("TSC2", client=bad), [])

    def test_rank_is_union_rank(self):
        """The 'rank' field in rescue_genes output is the union_rank from the DB."""
        rows = self.rescue_genes("TSC2", client=self.client)
        # DCTN6 has union_rank=2 in fixture; FZD7 has union_rank=4
        self.assertEqual(rows[0]["rank"], 2)   # DCTN6 union_rank
        self.assertEqual(rows[1]["rank"], 4)   # FZD7 union_rank


class TestMoatFactsUnavailableClient(unittest.TestCase):

    def test_unavailable_client_returns_empty_list(self):
        from moat.client import MoatClient
        from moat.facts import moat_facts
        bad_client = MoatClient(db_path="/tmp/__no_such_moat_for_facts_test__.sqlite")
        result = moat_facts("TSC2", client=bad_client)
        self.assertEqual(result, [])

    def test_unavailable_client_no_raise(self):
        from moat.client import MoatClient
        from moat.facts import moat_facts
        bad_client = MoatClient(db_path="/tmp/__no_such_moat_for_facts_test_2__.sqlite")
        try:
            moat_facts("TSC2", client=bad_client)
        except Exception as e:
            self.fail(f"moat_facts raised unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()
