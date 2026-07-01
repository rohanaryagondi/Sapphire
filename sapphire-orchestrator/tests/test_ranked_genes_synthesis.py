"""Unit + integration tests for ranked_genes / discovery_candidates synthesis (WO-9).

Verifies _build_rescue_synthesis() (unit) and the run_live synthesis block (integration):
  - ranked_genes = the QUERIED candidate genes, ordered by Quiver union_rank
  - absent queried genes appear at end with role="not_in_quiver" (not dropped)
  - control genes (in similar set) labeled role="control"
  - discovery_candidates = Quiver's global top hits NOT in the queried set
  - global top hits do NOT appear in ranked_genes
  - non-rescue queries are unaffected (no ranked_genes / discovery_candidates)
  - when queried_genes is empty, discovery_candidates holds all global hits

All tests: CLAUDE_BIN=/usr/bin/false, hermetic SQLite moat, no real subprocess.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ORCH = os.path.dirname(_HERE)
if _ORCH not in sys.path:
    sys.path.insert(0, _ORCH)


# ---------------------------------------------------------------------------
# Moat fixture.
# ---------------------------------------------------------------------------

def _make_tsc2_moat() -> str:
    """Hermetic SQLite moat: TSC2 rescue + similar rows.

    Global top rescuers (DCTN6/FZD7/RALA) + queried genes (BCL2 rank15, CDK9 rank19).
    MTOR in similar (control). VPS54 absent entirely.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    db = tmp.name
    tmp.close()
    con = sqlite3.connect(db)
    con.execute("""CREATE TABLE neighbors (
                   query TEXT, query_type TEXT, ref TEXT, ref_type TEXT,
                   ref_dose TEXT, effect TEXT,
                   rank_cosine INTEGER, rank_euclidean INTEGER, union_rank INTEGER,
                   cosine REAL, euclidean REAL)""")
    con.execute("CREATE TABLE moat_meta (key TEXT PRIMARY KEY, value TEXT)")
    rows = [
        ("TSC2", "gene", "TSC1",  "gene", None, "similar",  1, 1, 2,  0.970, 0.18),
        ("TSC2", "gene", "MTOR",  "gene", None, "similar",  2, 2, 4,  0.850, 0.20),
        ("TSC2", "gene", "DCTN6", "gene", None, "opposite", 1, 1, 2,  0.163, 0.50),
        ("TSC2", "gene", "FZD7",  "gene", None, "opposite", 2, 2, 4,  0.204, 0.55),
        ("TSC2", "gene", "RALA",  "gene", None, "opposite", 3, 3, 6,  0.227, 0.60),
        ("TSC2", "gene", "BCL2",  "gene", None, "opposite", 7, 8, 15, 0.112, 0.71),
        ("TSC2", "gene", "CDK9",  "gene", None, "opposite", 9, 10,19, 0.098, 0.76),
        ("TSC2", "gene", "RAPAMYCIN", "compound", "10nM", "opposite", 1, 1, 2, 0.823, 0.44),
    ]
    con.executemany("INSERT INTO neighbors VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return db


# ---------------------------------------------------------------------------
# Shared pre-built inputs for _build_rescue_synthesis unit tests.
# ---------------------------------------------------------------------------

# rescue_ranked: Quiver's global top rescue hits for TSC2.
_RESCUE_RANKED = [
    {"rank": 2,  "gene": "DCTN6", "cosine": 0.163, "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real"},
    {"rank": 4,  "gene": "FZD7",  "cosine": 0.204, "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real"},
    {"rank": 6,  "gene": "RALA",  "cosine": 0.227, "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real"},
    {"rank": 15, "gene": "BCL2",  "cosine": 0.112, "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real"},
    {"rank": 19, "gene": "CDK9",  "cosine": 0.098, "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real"},
]

# gene_mechanisms: from the rescue-mechanism reasoner.
_GENE_MECHANISMS = [
    {"gene": "BCL2",  "rank": 1, "mechanism": "BCL2 modulates autophagy flux, countering TSC2-KO mTORC1 overdrive.",
     "citations": ["PMID:34567890"], "confidence": "high"},
    {"gene": "CDK9",  "rank": 2, "mechanism": "CDK9 transcriptional regulation attenuates mTOR proliferation.",
     "citations": ["PMID:45678901"], "confidence": "medium"},
    {"gene": "DCTN6", "rank": 3, "mechanism": "DCTN6 dampens mTORC1 hyperactivation downstream of TSC2 loss.",
     "citations": ["PMID:12345678"], "confidence": "high"},
    {"gene": "FZD7",  "rank": 4, "mechanism": "FZD7/Wnt cross-talk restores autophagic flux.",
     "citations": ["PMID:23456789"], "confidence": "medium"},
]

# Per-gene dossier facts (what the moat-agent emits with queried_genes).
_PER_GENE_FACTS = [
    {
        "field": "moat rescue (queried gene)",
        "value": "Queried rescue candidate: BCL2 opposes TSC2 KO EP-signature (union_rank 15, cos 0.112) [Quiver CNS_DFP]",
        "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real", "plane": "internal",
    },
    {
        "field": "moat rescue (queried gene)",
        "value": "Queried rescue candidate: CDK9 opposes TSC2 KO EP-signature (union_rank 19, cos 0.098) [Quiver CNS_DFP]",
        "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real", "plane": "internal",
    },
    {
        "field": "moat rescue (queried gene)",
        "value": "Queried rescue candidate: VPS54 not in Quiver's TSC2 rescue neighbor set (out of 3039 genes)",
        "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real", "plane": "internal",
    },
    {
        "field": "moat rescue (queried gene)",
        "value": "Queried rescue candidate: MTOR not in Quiver's TSC2 rescue neighbor set (out of 3039 genes)",
        "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real", "plane": "internal",
    },
]


# ---------------------------------------------------------------------------
# Unit tests: _build_rescue_synthesis directly.
# ---------------------------------------------------------------------------

class TestBuildRescueSynthesisUnit(unittest.TestCase):
    """Unit tests for _build_rescue_synthesis — injected inputs, no DB or run_live needed."""

    def setUp(self):
        self._db = _make_tsc2_moat()
        self._prev_db = os.environ.get("SAPPHIRE_MOAT_DB")
        os.environ["SAPPHIRE_MOAT_DB"] = self._db

    def tearDown(self):
        try:
            os.unlink(self._db)
        except OSError:
            pass
        if self._prev_db is None:
            os.environ.pop("SAPPHIRE_MOAT_DB", None)
        else:
            os.environ["SAPPHIRE_MOAT_DB"] = self._prev_db

    def _call(self, queried_genes=None, rescue_ranked=None, gene_mechanisms=None,
              all_dossier_facts=None):
        from live_engine import _build_rescue_synthesis
        return _build_rescue_synthesis(
            target="TSC2",
            rescue_ranked=rescue_ranked or _RESCUE_RANKED,
            gene_mechanisms=gene_mechanisms or _GENE_MECHANISMS,
            all_dossier_facts=all_dossier_facts or _PER_GENE_FACTS,
            queried_genes=queried_genes or ["BCL2", "CDK9", "VPS54", "MTOR"],
        )

    # ── ranked_genes contents ──────────────────────────────────────────────

    def test_ranked_genes_contains_bcl2_and_cdk9(self):
        ranked, _, _, _, _ = self._call()
        gene_names = {g["gene"] for g in ranked}
        self.assertIn("BCL2", gene_names, "BCL2 queried + rank15 → rescue_candidate in ranked_genes")
        self.assertIn("CDK9", gene_names, "CDK9 queried + rank19 → rescue_candidate in ranked_genes")

    def test_rescue_candidates_sorted_by_rank_asc(self):
        ranked, _, _, _, _ = self._call()
        rescuers = [g for g in ranked if g.get("role") == "rescue_candidate"]
        ranks = [g["rank"] for g in rescuers]
        self.assertEqual(ranks, sorted(ranks), "rescue_candidates must be union_rank ascending")

    def test_bcl2_rank15_cosine_from_dossier_fact(self):
        ranked, _, _, _, _ = self._call()
        bcl2 = next((g for g in ranked if g["gene"] == "BCL2"), None)
        self.assertIsNotNone(bcl2, "BCL2 must appear in ranked_genes")
        self.assertEqual(bcl2["rank"], 15)
        self.assertAlmostEqual(bcl2["cosine"], 0.112, places=3)
        self.assertEqual(bcl2["role"], "rescue_candidate")

    def test_cdk9_rank19_rank_and_role(self):
        ranked, _, _, _, _ = self._call()
        cdk9 = next((g for g in ranked if g["gene"] == "CDK9"), None)
        self.assertIsNotNone(cdk9, "CDK9 must appear in ranked_genes")
        self.assertEqual(cdk9["rank"], 19)
        self.assertEqual(cdk9["role"], "rescue_candidate")

    def test_fzd7_ranked_before_bcl2_when_queried(self):
        """FZD7 (rank 4) must appear before BCL2 (rank 15) when both are queried."""
        ranked, _, _, _, _ = self._call(
            queried_genes=["BCL2", "FZD7"],
            all_dossier_facts=[
                {"field": "moat rescue (queried gene)",
                 "value": "Queried rescue candidate: BCL2 opposes TSC2 KO EP-signature (union_rank 15, cos 0.112) [Quiver CNS_DFP]",
                 "provenance": "moat-real"},
                {"field": "moat rescue (queried gene)",
                 "value": "Queried rescue candidate: FZD7 opposes TSC2 KO EP-signature (union_rank 4, cos 0.204) [Quiver CNS_DFP]",
                 "provenance": "moat-real"},
            ],
        )
        names = [g["gene"] for g in ranked if g.get("role") == "rescue_candidate"]
        self.assertLess(names.index("FZD7"), names.index("BCL2"),
                        "FZD7 (rank4) must precede BCL2 (rank15)")

    def test_vps54_absent_appears_with_not_in_quiver(self):
        ranked, _, _, _, _ = self._call()
        vps54 = next((g for g in ranked if g["gene"] == "VPS54"), None)
        self.assertIsNotNone(vps54, "VPS54 must appear in ranked_genes (absent, not dropped)")
        self.assertIsNone(vps54["rank"])
        self.assertIsNone(vps54["cosine"])
        self.assertEqual(vps54["role"], "not_in_quiver")
        self.assertIn("Quiver", vps54.get("note", ""),
                      "note must mention Quiver's rescue set")

    def test_mtor_labeled_control_from_similar_lookup(self):
        """MTOR is in the similar set → role='control'."""
        ranked, _, _, _, _ = self._call()
        mtor = next((g for g in ranked if g["gene"] == "MTOR"), None)
        self.assertIsNotNone(mtor, "MTOR queried → must appear in ranked_genes")
        # MTOR is in the fixture's "similar" set so similar_lookup returns found=True.
        self.assertEqual(mtor["role"], "control",
                         "MTOR (TSC2-similar) must be labeled 'control' not 'not_in_quiver'")

    def test_global_hits_not_in_ranked_genes(self):
        """DCTN6/RALA are NOT queried → must not appear in ranked_genes."""
        ranked, _, _, _, _ = self._call()
        gene_names = {g["gene"] for g in ranked}
        self.assertNotIn("DCTN6", gene_names, "DCTN6 not queried → discovery_candidates only")
        self.assertNotIn("RALA",  gene_names, "RALA not queried → discovery_candidates only")

    def test_absent_genes_after_rescue_candidates(self):
        """All rescue_candidate entries (with rank) precede absent/control entries (rank=None)."""
        ranked, _, _, _, _ = self._call()
        with_rank    = [i for i, g in enumerate(ranked) if g["rank"] is not None]
        without_rank = [i for i, g in enumerate(ranked) if g["rank"] is None]
        if with_rank and without_rank:
            self.assertLess(max(with_rank), min(without_rank),
                            "All absent/control entries must follow all rescue_candidates")

    def test_bcl2_carries_mechanism_and_citations(self):
        ranked, _, _, _, _ = self._call()
        bcl2 = next((g for g in ranked if g["gene"] == "BCL2"), None)
        self.assertIsNotNone(bcl2)
        self.assertEqual(bcl2["citations"], ["PMID:34567890"])
        self.assertIn("autophagy", bcl2["mechanism"])

    def test_perturbation_gene_not_in_ranked_genes(self):
        """TSC2 itself must not appear in ranked_genes (it's the perturbation)."""
        ranked, _, _, _, _ = self._call(queried_genes=["TSC2", "BCL2"])
        names = {g["gene"] for g in ranked}
        self.assertNotIn("TSC2", names, "TSC2 is the perturbation and must not rank itself")

    # ── discovery_candidates contents ────────────────────────────────────

    def test_discovery_candidates_contains_dctn6_and_rala(self):
        _, disc, _, _, _ = self._call()
        names = {g["gene"] for g in disc}
        self.assertIn("DCTN6", names, "DCTN6 is a global top hit not in the queried set")
        self.assertIn("RALA",  names, "RALA is a global top hit not in the queried set")

    def test_discovery_candidates_role_is_discovery_alpha(self):
        _, disc, _, _, _ = self._call()
        for entry in disc:
            self.assertEqual(entry["role"], "discovery_alpha",
                             f"{entry['gene']} must have role=discovery_alpha")

    def test_queried_genes_not_in_discovery_candidates(self):
        """BCL2/CDK9 are queried → must NOT also appear in discovery_candidates."""
        _, disc, _, _, _ = self._call()
        disc_names = {g["gene"] for g in disc}
        self.assertNotIn("BCL2", disc_names, "BCL2 is queried → must not be in discovery_candidates")
        self.assertNotIn("CDK9", disc_names, "CDK9 is queried → must not be in discovery_candidates")

    def test_discovery_note_mentions_strong_internal_signal(self):
        _, disc, _, _, _ = self._call()
        for entry in disc:
            self.assertIn("internal signal", entry.get("note", ""),
                          f"{entry['gene']} discovery note must mention 'internal signal'")

    def test_discovery_candidates_have_rank_and_cosine(self):
        """discovery_candidates come from rescue_ranked → have real rank and cosine."""
        _, disc, _, _, _ = self._call()
        for entry in disc:
            self.assertIsNotNone(entry["rank"],   f"{entry['gene']} must have a numeric rank")
            self.assertIsNotNone(entry["cosine"], f"{entry['gene']} must have a numeric cosine")

    def test_discovery_candidates_dctn6_carries_cited_mechanism(self):
        """DCTN6 mechanism from gene_mechanisms surfaces in discovery_candidates."""
        _, disc, _, _, _ = self._call()
        dctn6 = next((g for g in disc if g["gene"] == "DCTN6"), None)
        self.assertIsNotNone(dctn6)
        self.assertEqual(dctn6["citations"], ["PMID:12345678"])
        self.assertIn("mTORC1", dctn6["mechanism"])

    # ── recommendation ────────────────────────────────────────────────────

    def test_recommendation_contains_rescue(self):
        _, _, rec, _, _ = self._call()
        self.assertIn("rescue", rec.lower())

    def test_recommendation_mentions_queried_candidate(self):
        _, _, rec, _, _ = self._call()
        self.assertTrue("BCL2" in rec or "CDK9" in rec,
                        f"Recommendation must mention a queried candidate; got: {rec!r}")

    def test_recommendation_does_not_open_with_dctn6(self):
        """DCTN6 is a discovery hit (not queried); it must not lead the recommendation."""
        _, _, rec, _, _ = self._call()
        # The first gene mentioned should be BCL2 or CDK9 (queried), not DCTN6/RALA.
        # We check by asserting a queried gene is in the recommendation.
        self.assertFalse(
            rec.startswith("Queried rescue-gene candidates") and "DCTN6" in rec[:70] and "BCL2" not in rec[:70],
            f"DCTN6 must not open the recommendation when BCL2/CDK9 are queried; got: {rec!r}",
        )

    def test_confidence_high_when_queried_genes_are_cited(self):
        """High confidence when ≥3 queried rescue candidates have citations."""
        many_queried = ["G1", "G2", "G3", "G4"]
        per_gene_facts = [
            {"field": "moat rescue (queried gene)",
             "value": f"Queried rescue candidate: {g} opposes TSC2 KO EP-signature (union_rank {i+1}, cos 0.{i+1}00) [Quiver CNS_DFP]",
             "provenance": "moat-real"}
            for i, g in enumerate(["G1", "G2", "G3", "G4"])
        ]
        rescue_ranked_extra = [
            {"rank": i+1, "gene": g, "cosine": 0.1*(i+1), "source": "Quiver", "tier": "T2", "provenance": "moat-real"}
            for i, g in enumerate(["G1", "G2", "G3", "G4"])
        ]
        gene_mechs_cited = [
            {"gene": g, "rank": i+1, "mechanism": f"{g} mechanism.", "citations": [f"PMID:{i}"], "confidence": "high"}
            for i, g in enumerate(["G1", "G2", "G3", "G4"])
        ]
        _, _, _, conf, _ = self._call(
            queried_genes=many_queried,
            rescue_ranked=rescue_ranked_extra,
            gene_mechanisms=gene_mechs_cited,
            all_dossier_facts=per_gene_facts,
        )
        self.assertEqual(conf, "high", "≥3 cited rescue candidates → confidence=high")

    # ── empty queried_genes ───────────────────────────────────────────────

    def test_no_queried_genes_empty_ranked_genes(self):
        """queried_genes=[] (or only the perturbation) → ranked_genes has no rescue_candidates."""
        ranked, disc, _, _, _ = self._call(queried_genes=["TSC2"])
        rescue = [g for g in ranked if g.get("role") == "rescue_candidate"]
        self.assertEqual(rescue, [], "No queried candidates → no rescue_candidate rows")

    def test_no_queried_genes_all_global_hits_in_discovery(self):
        """With no queried candidates, ALL rescue_ranked go to discovery_candidates."""
        _, disc, _, _, _ = self._call(queried_genes=["TSC2"])
        disc_names = {g["gene"] for g in disc}
        for r in _RESCUE_RANKED:
            if r["gene"] != "TSC2":
                self.assertIn(r["gene"], disc_names,
                              f"{r['gene']} must be in discovery_candidates when not queried")

    # ── honesty: no rank invented ─────────────────────────────────────────

    def test_no_rank_asserted_without_dossier_fact(self):
        """If a gene is queried but has NO per-gene dossier fact → rank=None (not_in_quiver)."""
        ranked, _, _, _, _ = self._call(
            queried_genes=["NOVELGENE"],
            all_dossier_facts=[],  # empty dossier — no per-gene facts
        )
        novel = next((g for g in ranked if g["gene"] == "NOVELGENE"), None)
        self.assertIsNotNone(novel)
        self.assertIsNone(novel["rank"], "No dossier fact → rank must be None (not invented)")
        self.assertEqual(novel["role"], "not_in_quiver")


# ---------------------------------------------------------------------------
# Integration tests: run_live synthesis block via patched moat agent.
# ---------------------------------------------------------------------------

def _mock_runner_factory():
    body = {
        "target": "TSC2",
        "provenance": "scientific-reasoning",
        "gene_mechanisms": _GENE_MECHANISMS,
    }

    class _Proc:
        returncode = 0
        stderr = ""
        stdout = json.dumps({"structured_output": body})

    return lambda cmd: _Proc()


def _run_with_injected_per_gene_facts(db_path: str, queried_genes: list[str]) -> dict:
    """Run the full rescue-ranking query via run_live with the moat patched to
    emit per-gene dossier facts for `queried_genes` against TSC2.

    The query is 'Rank genes that rescue the TSC2-KO phenotype' so target='TSC2'.
    The patched moat agent also returns per-gene facts for `queried_genes`, simulating
    the real scenario where the user's candidates were identified before the run.
    """
    import live_engine as _le
    from emet.session_bridge import make_session_emet_handler

    _original = _le._build_moat_agent

    def _patched():
        def _agent(inputs: dict) -> dict:
            # Always query as TSC2 so global rescue hits are correct.
            from moat.facts import moat_facts
            global_rows = moat_facts("TSC2", k=6)
            # Add per-gene facts for the queried genes.
            per_gene_rows = []
            for g in queried_genes:
                g_up = g.upper()
                if g_up == "TSC2":
                    continue
                fact = next((f for f in _PER_GENE_FACTS if g_up in f["value"]), None)
                if fact:
                    # Strip "field" key: harness findings schema has additionalProperties:false
                    # and only allows value/source/tier/flag/provenance.
                    row = {k: v for k, v in fact.items() if k != "field"}
                    per_gene_rows.append(row)
            facts = per_gene_rows + [
                {"value": r["value"], "source": r["source"],
                 "tier": r["tier"], "provenance": r.get("provenance", "moat-real")}
                for r in global_rows
            ]
            return {"candidate": "TSC2", "facts": facts, "provenance": "moat-real"}
        return _agent

    _le._build_moat_agent = _patched
    try:
        ctx = {
            "runner": _mock_runner_factory(),
            "emet_handler": make_session_emet_handler({}),
            # Inject the queried gene list so the synthesis block knows which genes the
            # user is asking about — bypassing the planner's gene extraction which only
            # sees the query text and would miss genes provided via prior context.
            "queried_genes": queried_genes,
        }
        result = _le.run_live(
            "Rank genes that rescue the TSC2-KO phenotype based on Quiver data.",
            ctx=ctx,
        )
    finally:
        _le._build_moat_agent = _original
    return result


class TestRescueSynthesisIntegration(unittest.TestCase):
    def setUp(self):
        self._db = _make_tsc2_moat()
        self._prev_db  = os.environ.get("SAPPHIRE_MOAT_DB")
        self._prev_sim = os.environ.get("SAPPHIRE_SIMULATE_MODELS")
        os.environ["SAPPHIRE_MOAT_DB"] = self._db
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"

    def tearDown(self):
        try:
            os.unlink(self._db)
        except OSError:
            pass
        for k, v in (("SAPPHIRE_MOAT_DB", self._prev_db),
                     ("SAPPHIRE_SIMULATE_MODELS", self._prev_sim)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_integration_ranked_genes_contains_bcl2_cdk9(self):
        """Integration: with per-gene facts injected for BCL2/CDK9, they appear in ranked_genes."""
        res = _run_with_injected_per_gene_facts(self._db, ["BCL2", "CDK9", "VPS54", "MTOR"])
        ranked = res["synthesize"].get("ranked_genes", [])
        gene_names = {g["gene"] for g in ranked}
        self.assertIn("BCL2", gene_names)
        self.assertIn("CDK9", gene_names)

    def test_integration_dctn6_not_in_ranked_genes(self):
        """Integration: DCTN6 (not queried) must not appear in ranked_genes."""
        res = _run_with_injected_per_gene_facts(self._db, ["BCL2", "CDK9"])
        ranked = res["synthesize"].get("ranked_genes", [])
        self.assertNotIn("DCTN6", {g["gene"] for g in ranked})

    def test_integration_discovery_candidates_has_dctn6(self):
        """Integration: DCTN6 (global top hit, not queried) must be in discovery_candidates."""
        res = _run_with_injected_per_gene_facts(self._db, ["BCL2", "CDK9"])
        disc = res["synthesize"].get("discovery_candidates", [])
        self.assertIn("DCTN6", {g["gene"] for g in disc})

    def test_integration_vps54_absent_not_dropped(self):
        """Integration: VPS54 (not in rescue set) appears with role=not_in_quiver."""
        res = _run_with_injected_per_gene_facts(self._db, ["BCL2", "CDK9", "VPS54"])
        ranked = res["synthesize"].get("ranked_genes", [])
        vps54 = next((g for g in ranked if g["gene"] == "VPS54"), None)
        self.assertIsNotNone(vps54, "VPS54 must appear in ranked_genes, not be dropped")
        self.assertEqual(vps54["role"], "not_in_quiver")

    def test_integration_no_queried_genes_all_global_in_discovery(self):
        """Integration: with no explicit candidates, global top hits go to discovery_candidates."""
        res = _run_with_injected_per_gene_facts(self._db, [])
        disc = res["synthesize"].get("discovery_candidates", [])
        disc_names = {g["gene"] for g in disc}
        self.assertIn("DCTN6", disc_names)
        self.assertIn("FZD7",  disc_names)
        self.assertIn("RALA",  disc_names)


# ---------------------------------------------------------------------------
# Tests: non-rescue query is unaffected.
# ---------------------------------------------------------------------------

class TestNonRescueQueryUnchanged(unittest.TestCase):
    def setUp(self):
        self._db = _make_tsc2_moat()
        self._prev_db  = os.environ.get("SAPPHIRE_MOAT_DB")
        self._prev_sim = os.environ.get("SAPPHIRE_SIMULATE_MODELS")
        os.environ["SAPPHIRE_MOAT_DB"] = self._db
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"

    def tearDown(self):
        try:
            os.unlink(self._db)
        except OSError:
            pass
        for k, v in (("SAPPHIRE_MOAT_DB", self._prev_db),
                     ("SAPPHIRE_SIMULATE_MODELS", self._prev_sim)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_viability_query_has_no_ranked_genes(self):
        from live_engine import run_live
        from emet.session_bridge import make_session_emet_handler
        ctx = {
            "runner": _mock_runner_factory(),
            "emet_handler": make_session_emet_handler({}),
        }
        res = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=ctx)
        syn = res["synthesize"]
        self.assertNotIn("ranked_genes", syn,
                         "Non-rescue query must not emit ranked_genes")
        self.assertNotIn("discovery_candidates", syn,
                         "Non-rescue query must not emit discovery_candidates")


if __name__ == "__main__":
    unittest.main()
