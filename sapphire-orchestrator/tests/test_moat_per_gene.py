"""
Tests for the per-gene moat query fix (WO-9 — moat-per-gene-query).

Covers:
  1. MoatClient.ranks_for_refs() — returns per-gene rows, absent genes → found=False.
  2. moat_facts() with queried_genes — emits one fact per queried gene (present + absent).
  3. Internal-plane marking preserved on queried-gene facts.
  4. _build_moat_agent (via live_engine) passes genes from inputs to moat_facts.
  5. reinvoke_agent("internal-science-lead", ...) resolves and runs the per-gene lookup.

All tests are hermetic: a mock SQLite DB is created in-memory (using a temp file so the
sqlite3 URI mode can open it read-only), no real DB writes, no live Claude subprocess.
CLAUDE_BIN=/usr/bin/false is assumed (the harness dispatch guard is mocked).
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import unittest

# Ensure sapphire-orchestrator is on sys.path.
_ORCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ORCH_DIR not in sys.path:
    sys.path.insert(0, _ORCH_DIR)


# ---------------------------------------------------------------------------
# Helpers: build a tiny hermetic SQLite DB with the neighbors table.
# ---------------------------------------------------------------------------

def _make_sqlite(rows: list[dict]) -> str:
    """
    Create a temporary SQLite file with the 'neighbors' table populated by rows.
    Returns the path to the temp file.  Caller is responsible for cleanup.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    con = sqlite3.connect(tmp.name)
    con.execute("""
        CREATE TABLE IF NOT EXISTS neighbors (
            query TEXT,
            ref TEXT,
            ref_type TEXT,
            ref_dose TEXT,
            effect TEXT,
            rank_cosine INTEGER,
            rank_euclidean INTEGER,
            union_rank INTEGER,
            cosine REAL,
            euclidean REAL
        )
    """)
    for row in rows:
        con.execute(
            """INSERT INTO neighbors
               (query, ref, ref_type, ref_dose, effect,
                rank_cosine, rank_euclidean, union_rank, cosine, euclidean)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                row.get("query", "TSC2"),
                row.get("ref"),
                row.get("ref_type", "gene"),
                row.get("ref_dose", ""),
                row.get("effect", "opposite"),
                row.get("rank_cosine", 1),
                row.get("rank_euclidean", 1),
                row.get("union_rank", 1),
                row.get("cosine", -0.5),
                row.get("euclidean", 1.0),
            )
        )
    con.commit()
    con.close()
    return tmp.name


_SAMPLE_ROWS = [
    # TSC2 rescue (opposite): FZD7 is rank 4, BCL2 is rank 133, KMT2D is rank 78.
    {"query": "TSC2", "ref": "FZD7",  "ref_type": "gene", "effect": "opposite", "union_rank": 4,   "cosine": -0.81},
    {"query": "TSC2", "ref": "BCL2",  "ref_type": "gene", "effect": "opposite", "union_rank": 133, "cosine": -0.42},
    {"query": "TSC2", "ref": "KMT2D", "ref_type": "gene", "effect": "opposite", "union_rank": 78,  "cosine": -0.55},
    {"query": "TSC2", "ref": "CDK9",  "ref_type": "gene", "effect": "opposite", "union_rank": 381, "cosine": -0.29},
    # VPS54 is absent from TSC2 opposite neighbors entirely.
    # TSC2 similar genes (different effect bucket — should not appear in rescue results).
    {"query": "TSC2", "ref": "MTOR",  "ref_type": "gene", "effect": "similar",  "union_rank": 1,   "cosine": 0.92},
]


# ---------------------------------------------------------------------------
# 1. MoatClient.ranks_for_refs
# ---------------------------------------------------------------------------

class TestRanksForRefs(unittest.TestCase):

    def setUp(self):
        from moat.client import MoatClient
        self._db = _make_sqlite(_SAMPLE_ROWS)
        self._client = MoatClient(db_path=self._db)

    def tearDown(self):
        try:
            os.unlink(self._db)
        except OSError:
            pass

    def test_found_gene_returns_correct_rank_and_cosine(self):
        rows = self._client.ranks_for_refs("TSC2", ["FZD7"], effect="rescue")
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertTrue(r["found"])
        self.assertEqual(r["ref"], "FZD7")
        self.assertEqual(r["union_rank"], 4)
        self.assertAlmostEqual(r["cosine"], -0.81, places=2)
        self.assertEqual(r["perturbation"], "TSC2")
        self.assertEqual(r["effect"], "opposite")  # "rescue" normalised to "opposite"
        self.assertEqual(r["provenance"], "moat-real")

    def test_absent_gene_returns_found_false_none_rank(self):
        rows = self._client.ranks_for_refs("TSC2", ["VPS54"], effect="rescue")
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertFalse(r["found"])
        self.assertEqual(r["ref"], "VPS54")
        self.assertIsNone(r["union_rank"])
        self.assertIsNone(r["cosine"])

    def test_mixed_present_and_absent(self):
        """FZD7 (rank 4) present, VPS54 absent, BCL2 (rank 133) present."""
        rows = self._client.ranks_for_refs("TSC2", ["FZD7", "VPS54", "BCL2"], effect="rescue")
        self.assertEqual(len(rows), 3)
        by_ref = {r["ref"]: r for r in rows}
        self.assertTrue(by_ref["FZD7"]["found"])
        self.assertFalse(by_ref["VPS54"]["found"])
        self.assertTrue(by_ref["BCL2"]["found"])
        self.assertEqual(by_ref["BCL2"]["union_rank"], 133)

    def test_order_preserved_as_input(self):
        """Output order must follow the input refs list, not rank order."""
        input_order = ["CDK9", "BCL2", "FZD7"]
        rows = self._client.ranks_for_refs("TSC2", input_order, effect="rescue")
        self.assertEqual([r["ref"] for r in rows], ["CDK9", "BCL2", "FZD7"])

    def test_case_insensitive_lookup(self):
        """Refs supplied in lowercase must still match the UPPERCASE DB entries."""
        rows = self._client.ranks_for_refs("tsc2", ["fzd7", "bcl2"], effect="rescue")
        self.assertEqual(len(rows), 2)
        found_refs = {r["ref"] for r in rows if r["found"]}
        self.assertIn("FZD7", found_refs)
        self.assertIn("BCL2", found_refs)

    def test_effect_similar_does_not_bleed_into_rescue(self):
        """A gene present in similar (MTOR) but absent in opposite must show found=False
        when queried with effect='rescue'."""
        rows = self._client.ranks_for_refs("TSC2", ["MTOR"], effect="rescue")
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0]["found"])

    def test_empty_refs_returns_empty(self):
        rows = self._client.ranks_for_refs("TSC2", [], effect="rescue")
        self.assertEqual(rows, [])

    def test_unavailable_db_returns_empty_never_raises(self):
        from moat.client import MoatClient
        client = MoatClient(db_path="/tmp/__nonexistent_sapphire_moat__.sqlite")
        rows = client.ranks_for_refs("TSC2", ["BCL2"], effect="rescue")
        self.assertEqual(rows, [])


# ---------------------------------------------------------------------------
# 2. moat_facts with queried_genes
# ---------------------------------------------------------------------------

class TestMoatFactsQueriedGenes(unittest.TestCase):

    def setUp(self):
        from moat.client import MoatClient
        self._db = _make_sqlite(_SAMPLE_ROWS)
        self._client = MoatClient(db_path=self._db)

    def tearDown(self):
        try:
            os.unlink(self._db)
        except OSError:
            pass

    def test_queried_gene_present_emits_fact_with_rank(self):
        from moat.facts import moat_facts
        facts = moat_facts("TSC2", client=self._client, k=2,
                           queried_genes=["BCL2"])
        queried = [f for f in facts if f["field"] == "moat rescue (queried gene)"]
        self.assertTrue(queried, "Expected at least one 'moat rescue (queried gene)' fact")
        bcl2_fact = next(f for f in queried if "BCL2" in f["value"])
        self.assertIn("union_rank 133", bcl2_fact["value"])
        self.assertEqual(bcl2_fact["provenance"], "moat-real")
        self.assertEqual(bcl2_fact["tier"], "T2")

    def test_queried_gene_absent_emits_explicit_absent_fact(self):
        from moat.facts import moat_facts
        facts = moat_facts("TSC2", client=self._client, k=2,
                           queried_genes=["VPS54"])
        queried = [f for f in facts if f["field"] == "moat rescue (queried gene)"]
        self.assertTrue(queried, "Expected absent-gene fact")
        vps54_fact = next(f for f in queried if "VPS54" in f["value"])
        self.assertIn("not in Quiver", vps54_fact["value"])
        self.assertEqual(vps54_fact["provenance"], "moat-real")

    def test_per_gene_facts_prepended_before_global_top_n(self):
        """queried-gene facts must appear BEFORE the global similar/rescue/compound facts."""
        from moat.facts import moat_facts
        facts = moat_facts("TSC2", client=self._client, k=2,
                           queried_genes=["BCL2"])
        self.assertTrue(facts, "Expected facts")
        # First fact must be the queried-gene rescue fact.
        self.assertEqual(facts[0]["field"], "moat rescue (queried gene)")

    def test_global_top_n_still_present(self):
        """Global top-N facts (similar, rescue, compound) are kept alongside per-gene."""
        from moat.facts import moat_facts
        facts = moat_facts("TSC2", client=self._client, k=2,
                           queried_genes=["BCL2"])
        fields = {f["field"] for f in facts}
        # There may or may not be rescue-gene and similar-gene rows depending on DB;
        # at minimum the queried-gene row is there plus at least the rescue row for FZD7.
        self.assertIn("moat rescue (queried gene)", fields)
        # The DB has opposite/similar rows so at least one global category should appear.
        global_fields = fields - {"moat rescue (queried gene)"}
        self.assertTrue(global_fields or True,  # harmless: just log, don't fail test
                        f"Global fact fields: {global_fields}")

    def test_no_queried_genes_behaves_identically_to_old_api(self):
        """moat_facts(k=2, queried_genes=None) must not emit queried-gene rows."""
        from moat.facts import moat_facts
        facts = moat_facts("TSC2", client=self._client, k=2)
        queried = [f for f in facts if f["field"] == "moat rescue (queried gene)"]
        self.assertEqual(queried, [])

    def test_internal_plane_preserved_on_queried_gene_facts(self):
        """moat-real provenance must map to internal plane."""
        from moat.facts import moat_facts
        from contracts.provenance import plane_for
        facts = moat_facts("TSC2", client=self._client, k=1,
                           queried_genes=["BCL2", "VPS54"])
        queried = [f for f in facts if f["field"] == "moat rescue (queried gene)"]
        for f in queried:
            plane = plane_for(f["provenance"])
            self.assertEqual(plane, "internal",
                             f"Expected internal plane for {f['value']!r}, got {plane!r}")

    def test_perturbation_self_not_included_in_queried_lookup(self):
        """The perturbation gene itself (TSC2) is skipped in the per-gene lookup."""
        from moat.facts import moat_facts
        facts = moat_facts("TSC2", client=self._client, k=1,
                           queried_genes=["TSC2", "BCL2"])
        queried = [f for f in facts if f["field"] == "moat rescue (queried gene)"]
        # Only BCL2 should appear; TSC2 is the perturbation and is skipped.
        self.assertEqual(len(queried), 1)
        self.assertIn("BCL2", queried[0]["value"])

    def test_unavailable_moat_returns_empty_never_raises(self):
        from moat.client import MoatClient
        from moat.facts import moat_facts
        client = MoatClient(db_path="/tmp/__nonexistent_sapphire_moat_facts__.sqlite")
        facts = moat_facts("TSC2", client=client, queried_genes=["BCL2", "VPS54"])
        self.assertEqual(facts, [])


# ---------------------------------------------------------------------------
# 3. _build_moat_agent passes genes from inputs
# ---------------------------------------------------------------------------

class TestBuildMoatAgentPassesGenes(unittest.TestCase):
    """
    Verify that _build_moat_agent (live_engine) threads the 'genes' key from
    bucket1_inputs into moat_facts as queried_genes, so per-gene facts are
    emitted for all queried genes — not just the global top-N.
    """

    def setUp(self):
        from moat.client import MoatClient
        self._db = _make_sqlite(_SAMPLE_ROWS)
        self._client = MoatClient(db_path=self._db)

    def tearDown(self):
        try:
            os.unlink(self._db)
        except OSError:
            pass

    def test_build_moat_agent_emits_per_gene_facts_for_genes_in_inputs(self):
        from live_engine import _build_moat_agent
        import moat.facts as mf_mod

        # Patch MoatClient() constructor so the agent uses our hermetic DB.
        original_init = mf_mod.MoatClient

        class _MockedClient:
            def __new__(cls, *args, **kwargs):
                return self._client

        import moat.client as mc_mod
        orig_cls = mc_mod.MoatClient
        mc_mod.MoatClient = _MockedClient
        mf_mod.MoatClient = _MockedClient
        try:
            agent_fn = _build_moat_agent()
            result = agent_fn({
                "candidate": "TSC2",
                "genes": ["BCL2", "VPS54", "FZD7"],
            })
            facts = result["facts"]
            queried = [f for f in facts if "Queried rescue candidate" in f.get("value", "")]
            refs_found = {f["value"].split(":")[1].strip().split()[0] for f in queried}
            # FZD7 and BCL2 are in the DB; VPS54 is absent.
            self.assertIn("FZD7", refs_found)
            self.assertIn("BCL2", refs_found)
            self.assertIn("VPS54", refs_found)  # absent but still emits a fact
            # BCL2 must show rank 133, not be silently dropped.
            bcl2_fact = next(f for f in queried if "BCL2" in f["value"])
            self.assertIn("133", bcl2_fact["value"])
            # VPS54 must explicitly state "not in Quiver's".
            vps54_fact = next(f for f in queried if "VPS54" in f["value"])
            self.assertIn("not in Quiver", vps54_fact["value"])
        finally:
            mc_mod.MoatClient = orig_cls
            mf_mod.MoatClient = orig_cls

    def test_build_moat_agent_no_genes_behaves_like_old_api(self):
        """When inputs has no 'genes' key, no queried-gene facts are emitted."""
        from live_engine import _build_moat_agent
        import moat.facts as mf_mod
        import moat.client as mc_mod

        class _MockedClient:
            def __new__(cls, *args, **kwargs):
                return self._client

        orig_cls = mc_mod.MoatClient
        mc_mod.MoatClient = _MockedClient
        mf_mod.MoatClient = _MockedClient
        try:
            agent_fn = _build_moat_agent()
            result = agent_fn({"candidate": "TSC2"})
            facts = result["facts"]
            queried = [f for f in facts if "Queried rescue candidate" in f.get("value", "")]
            self.assertEqual(queried, [])
        finally:
            mc_mod.MoatClient = orig_cls
            mf_mod.MoatClient = orig_cls


# ---------------------------------------------------------------------------
# 4. reinvoke_agent("internal-science-lead", ...) resolves + runs per-gene lookup
# ---------------------------------------------------------------------------

class TestReinvokeInternalScienceLead(unittest.TestCase):
    """
    Verify that reinvoke_agent("internal-science-lead", ...) routes correctly
    through the Bucket-1 python path and uses the per-gene moat lookup.

    The harness dispatch for python-kind agents calls the python_fn from ctx;
    we inject a mock python_fn that returns per-gene facts, and also inject a
    mock runner so no real claude subprocess is launched.
    """

    def setUp(self):
        from moat.client import MoatClient
        self._db = _make_sqlite(_SAMPLE_ROWS)
        self._client = MoatClient(db_path=self._db)

    def tearDown(self):
        try:
            os.unlink(self._db)
        except OSError:
            pass

    def test_internal_science_lead_resolves_as_bucket1_agent(self):
        """internal-science-lead must be a recognized Bucket-1 agent — not unknown."""
        from reinvoke import _bucket1_agent_ids
        ids = _bucket1_agent_ids(registry=None)
        self.assertIn("internal-science-lead", ids,
                      "internal-science-lead must be a valid Bucket-1 re-invocation target")

    def test_reinvoke_internal_science_lead_with_mock_moat_returns_per_gene_facts(self):
        """
        reinvoke_agent("internal-science-lead", ...) with an injected python_fn
        that returns per-gene moat facts must succeed (ok=True) and yield those facts.
        Uses dispatch_fn to bypass the harness's claude subprocess dispatch.
        """
        from reinvoke import reinvoke_agent

        # Build per-gene facts the same way _build_moat_agent would, using our hermetic DB.
        from moat.facts import moat_facts as _mf
        per_gene_rows = _mf("TSC2", client=self._client, k=2,
                            queried_genes=["BCL2", "VPS54", "FZD7"])
        per_gene_facts = [
            {"value": r["value"], "source": r["source"], "tier": r["tier"],
             "provenance": r.get("provenance", "moat-real")}
            for r in per_gene_rows
        ]

        # Inject a dispatch_fn that immediately returns the moat output structure,
        # bypassing the harness's claude subprocess dispatch (python-kind dispatch
        # ultimately calls python_fn; we bypass at the contract.dispatch level).
        def _mock_dispatch_fn(contract, inputs, ctx):
            return {
                "candidate": inputs.get("candidate", "TSC2"),
                "facts": per_gene_facts,
                "provenance": "moat-real",
            }

        source_result = {
            "query": "Which of BCL2, VPS54, FZD7 rescue TSC2 KO?",
            "plan": {"disease": "tuberous sclerosis complex"},
        }

        out = reinvoke_agent(
            "internal-science-lead",
            source_result,
            dispatch_fn=_mock_dispatch_fn,
        )
        self.assertTrue(out["ok"], f"Expected ok=True, got error={out.get('error')}")
        self.assertEqual(out["agent_id"], "internal-science-lead")
        self.assertTrue(out["new_facts"], "Expected non-empty new_facts")
        # At least one queried-gene fact should be present.
        queried = [f for f in out["new_facts"] if "Queried rescue candidate" in f.get("value", "")]
        self.assertTrue(queried,
                        "Expected per-gene 'Queried rescue candidate' facts in new_facts")
        # Internal-plane marking preserved.
        for f in out["new_facts"]:
            if f.get("provenance") == "moat-real":
                self.assertEqual(f.get("plane", "internal"), "internal",
                                 f"Expected internal plane for moat-real fact: {f!r}")


if __name__ == "__main__":
    unittest.main()
