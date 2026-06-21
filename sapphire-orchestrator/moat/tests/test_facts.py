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
