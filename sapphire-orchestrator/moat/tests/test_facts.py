"""
Tests for moat_facts (Task 4).

Builds a temp SQLite fixture with TSC2 rows (same schema as Task 2's test_client.py),
then asserts dossier-shaped fact rows are returned with provenance="moat-real".
All stdlib — no pyarrow, no pandas.
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
            query      TEXT,
            query_type TEXT,
            ref        TEXT,
            ref_type   TEXT,
            ref_dose   TEXT,
            effect     TEXT,
            rank       INTEGER,
            cosine     REAL,
            euclidean  REAL
        )
    """)
    cur.execute("""
        CREATE TABLE moat_meta (
            key   TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    rows = [
        ("TSC2", "gene", "TSC1",      "gene",     None,   "similar",  1, 0.97,  0.18),
        ("TSC2", "gene", "RHEB",      "gene",     None,   "similar",  2, 0.89,  0.31),
        # rescue GENES (opposite EP-signature genes) — the rescuers, rank-ordered.
        ("TSC2", "gene", "DCTN6",     "gene",     None,   "opposite", 1, 0.163, 0.50),
        ("TSC2", "gene", "FZD7",      "gene",     None,   "opposite", 2, 0.204, 0.55),
        ("TSC2", "gene", "RAPAMYCIN", "compound", "10nM", "opposite", 1, 0.823, 0.44),
    ]
    cur.executemany("INSERT INTO neighbors VALUES (?,?,?,?,?,?,?,?,?)", rows)
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
        # TSC1 row has cosine=0.97 (already 3dp); RAPAMYCIN has 0.823
        cpd_rows = [f for f in facts if f["field"] == "moat rescue (compound)"]
        self.assertTrue(any("0.823" in f["value"] for f in cpd_rows))

    def test_similar_genes_come_before_compounds(self):
        facts = self.moat_facts("TSC2", client=self.client)
        gene_indices = [i for i, f in enumerate(facts) if f["field"] == "moat similar (gene)"]
        cpd_indices  = [i for i, f in enumerate(facts) if f["field"] == "moat rescue (compound)"]
        if gene_indices and cpd_indices:
            self.assertLess(max(gene_indices), min(cpd_indices))

    def test_fact_has_required_keys(self):
        facts = self.moat_facts("TSC2", client=self.client)
        required = {"field", "value", "source", "tier", "provenance"}
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

    def test_rescue_genes_distinct_from_similar_genes(self):
        # The rescuers (opposite genes) must NOT be confused with the similar genes.
        facts = self.moat_facts("TSC2", client=self.client)
        rescue = {f["value"] for f in facts if f["field"] == "moat rescue (gene)"}
        similar = {f["value"] for f in facts if f["field"] == "moat similar (gene)"}
        self.assertTrue(any("DCTN6" in v for v in rescue))
        self.assertFalse(any("DCTN6" in v for v in similar))
        self.assertTrue(any("TSC1" in v for v in similar))
        self.assertFalse(any("TSC1" in v for v in rescue))


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
        rows = self.rescue_genes("TSC2", client=self.client)
        ranks = [r["rank"] for r in rows]
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(rows[0]["gene"], "DCTN6")  # rank 1

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
