"""
Tests for MoatClient (Task 2).

setUp builds a tiny in-memory-backed temp SQLite with the expected schema
and a handful of rows for TSC2. All stdlib — no pyarrow, no pandas.
"""
import os
import sqlite3
import tempfile
import unittest


class TestMoatClientAvailableAndNeighbors(unittest.TestCase):

    def setUp(self):
        # Create a named temp file so MoatClient can open it by path.
        self._tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._db_path = self._tmp.name
        self._tmp.close()

        con = sqlite3.connect(self._db_path)
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
        # Two similar genes for TSC2 (stored uppercase), one opposite compound
        rows = [
            ("TSC2", "gene", "TSC1",      "gene",     None,      "similar",  1, 0.97, 0.18),
            ("TSC2", "gene", "RHEB",      "gene",     None,      "similar",  2, 0.89, 0.31),
            ("TSC2", "gene", "RAPAMYCIN", "compound", "10nM",    "opposite", 1, 0.82, 0.44),
        ]
        cur.executemany(
            "INSERT INTO neighbors VALUES (?,?,?,?,?,?,?,?,?)", rows
        )
        cur.execute("INSERT INTO moat_meta VALUES ('version','test-1.0')")
        con.commit()
        con.close()

        # Import here so the test file can be parsed even when the module is absent
        # (Step 1: write failing test).
        from moat.client import MoatClient
        self.MoatClient = MoatClient
        self.client = MoatClient(db_path=self._db_path)

    def tearDown(self):
        os.unlink(self._db_path)

    # ------------------------------------------------------------------
    # available()
    # ------------------------------------------------------------------
    def test_available_true_with_real_db(self):
        self.assertTrue(self.client.available())

    # ------------------------------------------------------------------
    # neighbors() — case-insensitive query
    # ------------------------------------------------------------------
    def test_neighbors_case_insensitive_lowercase(self):
        rows = self.client.neighbors("tsc2", effect="similar")
        self.assertGreater(len(rows), 0)
        self.assertEqual(rows[0]["ref"], "TSC1")

    def test_neighbors_case_insensitive_mixed(self):
        rows = self.client.neighbors("Tsc2", effect="similar")
        self.assertGreater(len(rows), 0)

    def test_neighbors_similar_ordered_by_rank(self):
        rows = self.client.neighbors("TSC2", effect="similar")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["ref"], "TSC1")
        self.assertEqual(rows[1]["ref"], "RHEB")

    def test_neighbors_opposite_compound_filter(self):
        rows = self.client.neighbors("TSC2", effect="opposite", ref_type="compound")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ref"], "RAPAMYCIN")

    def test_neighbors_ref_type_filter_gene(self):
        rows = self.client.neighbors("TSC2", effect="similar", ref_type="gene")
        for row in rows:
            self.assertEqual(row["ref_type"], "gene")

    def test_neighbors_provenance_stamped(self):
        rows = self.client.neighbors("TSC2", effect="similar")
        for row in rows:
            self.assertEqual(row["provenance"], "moat-real")

    def test_neighbors_k_caps_results(self):
        rows = self.client.neighbors("TSC2", effect="similar", k=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ref"], "TSC1")

    def test_neighbors_no_match_returns_empty_list(self):
        rows = self.client.neighbors("NONEXISTENT_GENE_XYZ", effect="similar")
        self.assertEqual(rows, [])

    def test_neighbors_row_dict_keys(self):
        rows = self.client.neighbors("TSC2", effect="similar")
        expected_keys = {"query", "ref", "ref_type", "ref_dose", "effect", "rank",
                         "cosine", "euclidean", "provenance"}
        self.assertEqual(set(rows[0].keys()), expected_keys)

    # ------------------------------------------------------------------
    # health()
    # ------------------------------------------------------------------
    def test_health_shape(self):
        h = self.client.health()
        self.assertIn("available", h)
        self.assertIn("db_path", h)
        self.assertIn("n_rows", h)
        self.assertIn("meta", h)

    def test_health_available_true(self):
        h = self.client.health()
        self.assertTrue(h["available"])

    def test_health_n_rows(self):
        h = self.client.health()
        self.assertEqual(h["n_rows"], 3)

    def test_health_meta_version(self):
        h = self.client.health()
        self.assertEqual(h["meta"].get("version"), "test-1.0")


class TestMoatClientDefaultPath(unittest.TestCase):
    """Default db_path must resolve to <repo>/RohanOnly/moat/moat.sqlite."""

    def test_default_db_path_ends_with_repo_relative_path(self):
        # Unset env var so we fall through to the coded default
        original = os.environ.pop("SAPPHIRE_MOAT_DB", None)
        try:
            from moat.client import MoatClient
            from pathlib import Path
            client = MoatClient()
            # Normalise to a forward-slash string for cross-platform checking
            path = client.db_path.replace("\\", "/")
            # Derive the repo-root dir name at runtime so a clone in ANY directory
            # name passes (don't hardcode "sapphire-capability-map"). The test file
            # sits at <repo>/sapphire-orchestrator/moat/tests/, so parents[3] is the
            # repo root — the same root client.py resolves via parents[2].
            repo_root = Path(__file__).resolve().parents[3]
            expected_suffix = f"{repo_root.name}/RohanOnly/moat/moat.sqlite"
            self.assertTrue(
                path.endswith(expected_suffix),
                f"Default db_path does not end with expected suffix "
                f"{expected_suffix!r}: {path!r}",
            )
        finally:
            if original is not None:
                os.environ["SAPPHIRE_MOAT_DB"] = original


class TestMoatClientMissingDB(unittest.TestCase):
    """MoatClient pointed at a non-existent path must be safe."""

    def setUp(self):
        from moat.client import MoatClient
        self.client = MoatClient(db_path="/tmp/__no_such_moat_db_xyz__.sqlite")

    def test_available_false(self):
        self.assertFalse(self.client.available())

    def test_neighbors_returns_empty_no_raise(self):
        result = self.client.neighbors("TSC2", effect="similar")
        self.assertEqual(result, [])

    def test_health_available_false(self):
        h = self.client.health()
        self.assertFalse(h["available"])

    def test_health_n_rows_zero(self):
        h = self.client.health()
        self.assertEqual(h["n_rows"], 0)


class TestMoatProvenance(unittest.TestCase):
    def test_module_provenance_constant(self):
        import moat
        self.assertEqual(moat.PROVENANCE, "moat-real")

    def test_moat_client_importable(self):
        import moat
        self.assertTrue(hasattr(moat, "MoatClient"))


if __name__ == "__main__":
    unittest.main()
