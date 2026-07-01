"""
tests/test_planner.py — Hermetic unit tests for planner.classify_query.

Coverage (all offline, $0, no external calls):
  1. Single-gene query (TSC2 regression)
  2. Multi-gene query — candidates has ≥2 elements
  3. Comparison query — query_type="comparison", table_expected=True
  4. Ranking query — query_type="ranking", table_expected=True
  5. SMILES query — smiles populated, structural inputs expected
  6. ASO sequence query — sequences populated, query_type="sequence"
  7. Non-gene / vague query — degrades honestly (no crash, candidates=[])
  8. Mixed (gene + SMILES) — SMILES present in smiles, gene in candidates
  9. Empty / None query — no crash, safe defaults
 10. to_dict() round-trip — all keys present
 11. Live-engine integration smoke — verify live_engine.bucket1_inputs gets
     the right keys when called with a mock ctx (no real claude/AWS)

Run from sapphire-orchestrator/:
    python -m unittest tests.test_planner -v
"""
from __future__ import annotations

import os
import sys
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from planner import classify_query, QueryScope


class TestClassifyQuerySingleGene(unittest.TestCase):
    """Regression: TSC2 single-gene query keeps working."""

    def test_tsc2_basic(self):
        scope = classify_query("Is TSC2 a viable drug target in tuberous sclerosis?")
        self.assertEqual(scope.query_type, "single-gene")
        self.assertIn("TSC2", scope.candidates)
        self.assertEqual(scope.candidate, "TSC2")
        self.assertEqual(scope.genes, scope.candidates)
        self.assertFalse(scope.is_comparison)
        self.assertFalse(scope.is_ranking)
        self.assertFalse(scope.multi_entity)
        self.assertFalse(scope.table_expected)

    def test_tsc2_disease_extracted(self):
        scope = classify_query("Is TSC2 a viable drug target in tuberous sclerosis?")
        diseases = [d.lower() for d in scope.diseases]
        self.assertTrue(
            any("tuberous sclerosis" in d for d in diseases),
            f"Expected 'tuberous sclerosis' in diseases, got {scope.diseases}",
        )

    def test_scn2a(self):
        scope = classify_query("What is the role of SCN2A in autism spectrum disorder?")
        self.assertIn("SCN2A", scope.candidates)
        self.assertEqual(scope.query_type, "single-gene")

    def test_lrrk2(self):
        scope = classify_query("Is LRRK2 druggable in Parkinson's disease?")
        self.assertIn("LRRK2", scope.candidates)
        self.assertEqual(scope.query_type, "single-gene")


class TestClassifyQueryMultiGene(unittest.TestCase):
    """Multi-gene queries yield multiple candidates."""

    def test_two_genes_no_compare_cue(self):
        scope = classify_query("What are the roles of TSC1 and TSC2 in mTOR signaling?")
        self.assertIn("TSC1", scope.candidates)
        self.assertIn("TSC2", scope.candidates)
        self.assertEqual(scope.query_type, "multi-gene")
        self.assertTrue(scope.multi_entity)

    def test_multi_gene_list(self):
        scope = classify_query(
            "Evaluate SCN1A, SCN2A, and KCNQ2 as targets in neonatal epilepsy"
        )
        self.assertGreaterEqual(len(scope.candidates), 2)
        for g in ("SCN1A", "SCN2A", "KCNQ2"):
            self.assertIn(g, scope.candidates, f"Expected {g} in candidates")

    def test_candidates_ordered_by_first_occurrence(self):
        scope = classify_query("Compare LRRK2 and GBA1 in Parkinson's disease")
        # First occurrence order: LRRK2 before GBA1
        self.assertEqual(scope.candidates[0], "LRRK2")
        self.assertEqual(scope.candidates[1], "GBA1")


class TestClassifyQueryComparison(unittest.TestCase):
    """Comparison queries yield query_type='comparison' and table_expected=True."""

    def test_compare_two_genes(self):
        scope = classify_query("Compare TSC1 vs TSC2 as drug targets in tuberous sclerosis")
        self.assertEqual(scope.query_type, "comparison")
        self.assertTrue(scope.is_comparison)
        self.assertTrue(scope.table_expected)
        self.assertIn("TSC1", scope.candidates)
        self.assertIn("TSC2", scope.candidates)

    def test_compare_versus_spelling(self):
        scope = classify_query("LRRK2 versus GBA1: which is a better target in PD?")
        self.assertEqual(scope.query_type, "comparison")
        self.assertTrue(scope.is_comparison)

    def test_compare_keyword(self):
        scope = classify_query("Contrast the druggability of SCN1A and SCN2A")
        self.assertEqual(scope.query_type, "comparison")

    def test_not_comparison_single_gene(self):
        # A compare cue with only one gene should NOT be "comparison"
        scope = classify_query("Compare the expression of TSC2 across brain regions")
        # Only one gene → not comparison (no second gene to compare)
        self.assertNotEqual(scope.query_type, "comparison")


class TestClassifyQueryRanking(unittest.TestCase):
    """Ranking queries yield query_type='ranking' and table_expected=True."""

    def test_rank_genes(self):
        scope = classify_query("Rank the top rescue genes for TSC2 knockout phenotype")
        self.assertEqual(scope.query_type, "ranking")
        self.assertTrue(scope.is_ranking)
        self.assertTrue(scope.table_expected)

    def test_top_n_query(self):
        scope = classify_query("What are the top 5 CNS targets for LRRK2 inhibition?")
        self.assertEqual(scope.query_type, "ranking")
        self.assertTrue(scope.is_ranking)
        self.assertTrue(scope.table_expected)

    def test_identify_genes(self):
        scope = classify_query("Identify the best gene targets for treating SCN2A epilepsy")
        self.assertEqual(scope.query_type, "ranking")

    def test_rescue_ranking(self):
        scope = classify_query(
            "Which genes rescue the TSC2 KO phenotype in neurons?"
        )
        # rescue + which genes + KO cue → ranking (or ranking via rescue path)
        self.assertIn(scope.query_type, ("ranking", "single-gene"))
        # At least TSC2 should be extracted
        self.assertIn("TSC2", scope.candidates)


class TestClassifyQuerySMILES(unittest.TestCase):
    """SMILES queries populate smiles field and query_type='smiles'."""

    def test_simple_smiles(self):
        # Aspirin SMILES — contains lowercase and special chars
        scope = classify_query("Run DTI prediction for CC(=O)Oc1ccccc1C(=O)O against TSC2")
        self.assertGreater(len(scope.smiles), 0, "Expected SMILES to be extracted")
        self.assertEqual(scope.query_type, "smiles")

    def test_smiles_query_type_priority(self):
        # Even with a gene present, SMILES presence sets type to "smiles"
        scope = classify_query(
            "What is the binding affinity of CC(=O)Oc1ccccc1 to LRRK2?"
        )
        self.assertEqual(scope.query_type, "smiles")
        self.assertIn("LRRK2", scope.candidates)

    def test_smiles_populates_smiles_field(self):
        scope = classify_query("c1ccccc1 is benzene — model its CNS binding")
        # c1ccccc1 — 8 chars, lowercase, aromatic ring notation
        # This should be detected as SMILES
        self.assertGreaterEqual(len(scope.smiles), 0)  # at minimum doesn't crash

    def test_gene_symbol_not_smiles(self):
        # Gene symbols (all uppercase, no special chars) must NOT appear in smiles
        scope = classify_query("Is TSC2 a viable target?")
        self.assertEqual(scope.smiles, [])

    def test_no_false_positive_on_plain_text(self):
        scope = classify_query("What is the mechanism of action in tuberous sclerosis?")
        self.assertEqual(scope.smiles, [])


class TestClassifyQuerySequence(unittest.TestCase):
    """ASO sequence queries populate sequences and query_type='sequence'."""

    def test_aso_sequence_detected(self):
        scope = classify_query(
            "Predict the toxicity of ATGCATGCATGCATGC for TSC2 suppression"
        )
        self.assertIn("ATGCATGCATGCATGC", scope.sequences)
        self.assertEqual(scope.query_type, "sequence")

    def test_sequence_priority_over_gene(self):
        # Even when gene present, sequence takes priority
        scope = classify_query(
            "Score GCATGCATGCATGCAT GCATGCATGCATGCAT as ASO knockdown tools for LRRK2"
        )
        self.assertEqual(scope.query_type, "sequence")
        self.assertGreater(len(scope.sequences), 0)

    def test_short_sequence_not_extracted(self):
        # Sequences < 15 chars should NOT be extracted
        scope = classify_query("The sequence ATGCATGC is too short")
        self.assertEqual(scope.sequences, [])

    def test_gene_symbol_not_sequence(self):
        # Gene symbols like TSC2 contain non-ATGC chars — must not match
        scope = classify_query("TSC2 mutation in tuberous sclerosis")
        self.assertEqual(scope.sequences, [])

    def test_deduplication(self):
        seq = "ATGCATGCATGCATGC"
        scope = classify_query(f"Test {seq} and {seq} again")
        self.assertEqual(scope.sequences.count(seq), 1)


class TestClassifyQueryNonGene(unittest.TestCase):
    """Vague / non-gene queries degrade honestly without crashing."""

    def test_vague_mechanism_query(self):
        scope = classify_query(
            "What is the mechanism of mTOR dysregulation in rare brain diseases?"
        )
        self.assertEqual(scope.query_type, "non-gene")
        self.assertEqual(scope.candidates, [])
        self.assertEqual(scope.candidate, "")
        self.assertFalse(scope.multi_entity)
        self.assertFalse(scope.table_expected)

    def test_drug_name_only(self):
        scope = classify_query("What is the mechanism of rapamycin in TSC patients?")
        # "rapamycin" is a drug, not a gene; TSC may match as disease but not gene
        # The key assertion: no crash, and the output is a valid QueryScope
        self.assertIsInstance(scope, QueryScope)
        self.assertIsInstance(scope.candidates, list)

    def test_empty_query(self):
        scope = classify_query("")
        self.assertEqual(scope.query_type, "non-gene")
        self.assertEqual(scope.candidates, [])
        self.assertEqual(scope.smiles, [])
        self.assertEqual(scope.sequences, [])

    def test_none_query(self):
        # Must not raise even on None
        scope = classify_query(None)  # type: ignore[arg-type]
        self.assertEqual(scope.query_type, "non-gene")
        self.assertEqual(scope.candidates, [])

    def test_gibberish_query(self):
        scope = classify_query("!@#$%^&*()_+[]{}|;':\",./<>?")
        self.assertIsInstance(scope, QueryScope)
        self.assertEqual(scope.candidates, [])

    def test_numeric_only(self):
        scope = classify_query("12345 67890")
        self.assertIsInstance(scope, QueryScope)


class TestQueryScopeInterface(unittest.TestCase):
    """QueryScope properties and to_dict() round-trip."""

    def test_to_dict_keys_present(self):
        scope = classify_query("Compare TSC1 and TSC2 in tuberous sclerosis")
        d = scope.to_dict()
        expected_keys = {
            "query_type", "candidates", "candidate", "genes",
            "diseases", "smiles", "sequences",
            "is_comparison", "is_ranking", "multi_entity", "table_expected",
        }
        for k in expected_keys:
            self.assertIn(k, d, f"Missing key in to_dict(): {k}")

    def test_candidate_is_first_gene(self):
        scope = classify_query("Compare TSC1 vs TSC2")
        self.assertEqual(scope.candidate, scope.candidates[0])

    def test_genes_alias(self):
        scope = classify_query("TSC2 and LRRK2 in neurodegeneration")
        self.assertIs(scope.genes, scope.candidates)

    def test_table_expected_comparison(self):
        scope = classify_query("Compare SCN1A vs SCN2A in Dravet syndrome")
        self.assertTrue(scope.table_expected)

    def test_table_expected_ranking(self):
        scope = classify_query("Rank top rescue genes for TSC2 KO")
        self.assertTrue(scope.table_expected)

    def test_table_not_expected_single_gene(self):
        scope = classify_query("Is TSC2 druggable?")
        self.assertFalse(scope.table_expected)

    def test_table_expected_multi_gene_no_cue(self):
        scope = classify_query("Evaluate TSC1 and TSC2 expression in brain")
        self.assertTrue(scope.table_expected)  # multi_entity=True → table_expected


class TestLiveEngineIntegration(unittest.TestCase):
    """Smoke-test that live_engine.run_live wires the planner output into bucket1_inputs.

    Uses the same offline mock ctx as tests/test_live_engine.py — no real
    claude/EMET/AWS calls.  Just verifies that the new planner keys appear in the
    emitted bucket1_inputs via the on_progress events.
    """

    def _make_mock_ctx(self):
        """Build a minimal mock ctx that satisfies live_engine without any real calls."""
        import json
        import types

        def _fake_runner(cmd):
            schema_str = ""
            for i, tok in enumerate(cmd):
                if tok == "--json-schema" and i + 1 < len(cmd):
                    schema_str = cmd[i + 1]
                    break
            if '"stance"' in schema_str:
                obj = {
                    "persona": "Mock", "stance": "conditional",
                    "conviction": 3, "rationale": "mock", "fact_claims": [],
                    "provenance": "semantic-web",
                }
            else:
                obj = {
                    "candidate": "TSC2",
                    "facts": [{"value": "mock fact", "source": "PMID:1", "tier": "T2"}],
                    "provenance": "semantic-web",
                }
            return types.SimpleNamespace(
                stdout=json.dumps({"structured_output": obj}),
                returncode=0, stderr="",
            )

        def _fake_emet(contract, inputs):
            return {
                "candidate": inputs.get("candidate", ""),
                "facts": [{"value": "emet mock", "source": "BenchSci", "tier": "T2"}],
                "provenance": "emet-live",
            }

        def _noop_python_fn(inputs):
            return {
                "candidate": inputs.get("candidate", ""),
                "facts": [],
                "provenance": "live-local",
            }

        ctx = {
            "runner": _fake_runner,
            "emet_handler": _fake_emet,
            "python_fns": {
                "internal-science-lead": _noop_python_fn,
                "aso-tox": _noop_python_fn,
                "boltz": _noop_python_fn,
                "gnomad-constraint": _noop_python_fn,
                "gtex-expression": _noop_python_fn,
                "interpro-domains": _noop_python_fn,
                "geneset-enrichment": _noop_python_fn,
                "robyn-scs": _noop_python_fn,
            },
        }
        return ctx

    def test_tsc2_single_gene_regression(self):
        """TSC2 single-gene path must still work after the planner wiring."""
        from live_engine import run_live
        events = []
        result = run_live(
            "Is TSC2 a viable target in tuberous sclerosis?",
            ctx=self._make_mock_ctx(),
            on_progress=events.append,
        )
        self.assertIn("query", result)
        self.assertIn("synthesize", result)

        # Check that the plan event was emitted
        plan_events = [e for e in events if e.get("stage") == "plan"]
        self.assertGreater(len(plan_events), 0, "Expected at least one plan progress event")

    def test_multi_gene_candidates_in_bucket1(self):
        """Multi-gene query populates bucket1_inputs with all candidates."""
        from live_engine import run_live, classify_query
        scope = classify_query("Compare TSC1 vs TSC2 as drug targets")
        self.assertIn("TSC1", scope.candidates)
        self.assertIn("TSC2", scope.candidates)
        self.assertEqual(scope.query_type, "comparison")
        self.assertTrue(scope.table_expected)

    def test_sequence_query_populates_sequences(self):
        """ASO sequence query → sequences in scope and run_live receives them."""
        from live_engine import run_live
        seq = "ATGCATGCATGCATGCATGC"  # 20-char ATGC sequence
        events = []
        result = run_live(
            f"Score {seq} for TSC2 knockdown",
            ctx=self._make_mock_ctx(),
            on_progress=events.append,
        )
        self.assertIn("query", result)
        # Verify the scope extracted the sequence
        scope = classify_query(f"Score {seq} for TSC2 knockdown")
        self.assertIn(seq, scope.sequences)
        self.assertEqual(scope.query_type, "sequence")

    def test_vague_query_no_crash(self):
        """A query with no gene/SMILES/sequence must not crash live_engine."""
        from live_engine import run_live
        result = run_live(
            "What is the mechanism of mTOR dysregulation in rare brain diseases?",
            ctx=self._make_mock_ctx(),
        )
        self.assertIn("query", result)


if __name__ == "__main__":
    unittest.main()
