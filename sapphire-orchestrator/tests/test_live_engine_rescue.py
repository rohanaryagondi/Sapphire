"""Integration: the rescue-gene-ranking deliverable in run_live.

A "rank genes that rescue the TSC2-KO phenotype" query must:
  - detect the rescue-ranking intent,
  - pull the moat's OPPOSITE genes (the rescuers) as the ranked candidates,
  - run the simulate_exempt rescue-mechanism reasoner (REAL even under simulate; here a mock
    runner stands in for `claude -p` so CI never shells out),
  - emit a `synthesize.ranked_genes` table for the USER'S QUERIED GENES ordered by their
    Quiver EP-scores (not Quiver's global top rescue hits),
  - emit a `synthesize.discovery_candidates` table for Quiver's own global top hits NOT in
    the queried set (the discovery alpha),
  - and surface the rescue-mechanism step in the live progress stream.

An ordinary (non-rescue) query must be UNCHANGED (no ranked_genes; IND-style synthesis).

Uses a temp SQLite moat fixture (no RohanOnly dependency) + injected runner/EMET handler.
"""
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


def _make_fixture_moat() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    db = tmp.name
    tmp.close()
    con = sqlite3.connect(db)
    # WO-5 dual-rank schema: rank_cosine, rank_euclidean, union_rank replace 'rank'
    con.execute("""CREATE TABLE neighbors (
                   query TEXT, query_type TEXT, ref TEXT, ref_type TEXT,
                   ref_dose TEXT, effect TEXT,
                   rank_cosine INTEGER, rank_euclidean INTEGER, union_rank INTEGER,
                   cosine REAL, euclidean REAL)""")
    con.execute("CREATE TABLE moat_meta (key TEXT PRIMARY KEY, value TEXT)")
    # Tuple: (query, query_type, ref, ref_type, ref_dose, effect,
    #         rank_cosine, rank_euclidean, union_rank, cosine, euclidean)
    # Global top rescuers (DCTN6/FZD7/RALA) — Quiver's own discoveries, NOT queried genes.
    # Queried genes (BCL2/CDK9) have lower ranks.
    # MTOR is similar (same direction as KO) — a control; VPS54 is absent entirely.
    rows = [
        ("TSC2", "gene", "TSC1",      "gene",     None,   "similar",  1, 1, 2,  0.970, 0.18),
        ("TSC2", "gene", "MTOR",      "gene",     None,   "similar",  2, 2, 4,  0.850, 0.20),
        # the global top rescuers — opposite-signature genes, union_rank-ordered
        ("TSC2", "gene", "DCTN6",     "gene",     None,   "opposite", 1, 1, 2,  0.163, 0.50),
        ("TSC2", "gene", "FZD7",      "gene",     None,   "opposite", 2, 2, 4,  0.204, 0.55),
        ("TSC2", "gene", "RALA",      "gene",     None,   "opposite", 3, 3, 6,  0.227, 0.60),
        # queried genes (BCL2/CDK9 are rescue candidates at lower rank; VPS54 absent)
        ("TSC2", "gene", "BCL2",      "gene",     None,   "opposite", 7, 8, 15, 0.112, 0.71),
        ("TSC2", "gene", "CDK9",      "gene",     None,   "opposite", 9, 10,19, 0.098, 0.76),
        ("TSC2", "gene", "RAPAMYCIN", "compound", "10nM", "opposite", 1, 1, 2,  0.823, 0.44),
    ]
    con.executemany("INSERT INTO neighbors VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return db


def _mock_runner_factory():
    """A runner standing in for the rescue-mechanism `claude -p` call.

    Returns mechanisms for both the global top hits (DCTN6/FZD7) and queried genes
    (BCL2/CDK9) so either can surface cited mechanisms in ranked_genes or discovery_candidates.
    """
    body = {
        "target": "TSC2",
        "provenance": "scientific-reasoning",
        "gene_mechanisms": [
            {"gene": "DCTN6", "rank": 1,
             "mechanism": "Reversing DCTN6's signature dampens mTORC1 hyperactivation downstream of TSC2 loss.",
             "citations": ["PMID:12345678"], "confidence": "high"},
            {"gene": "FZD7", "rank": 2,
             "mechanism": "FZD7/Wnt cross-talk with mTORC1 may restore autophagic flux.",
             "citations": ["PMID:23456789"], "confidence": "medium"},
            {"gene": "BCL2", "rank": 3,
             "mechanism": "BCL2 modulates autophagy flux, partially countering TSC2-KO mTORC1 overdrive.",
             "citations": ["PMID:34567890"], "confidence": "high"},
            {"gene": "CDK9", "rank": 4,
             "mechanism": "CDK9 transcriptional regulation may attenuate mTOR-driven proliferation.",
             "citations": ["PMID:45678901"], "confidence": "medium"},
        ],
    }

    class _Proc:
        returncode = 0
        stderr = ""
        stdout = json.dumps({"structured_output": body})

    def runner(cmd):
        return _Proc()

    return runner


class _Base(unittest.TestCase):
    def setUp(self):
        self._db = _make_fixture_moat()
        self._prev_db = os.environ.get("SAPPHIRE_MOAT_DB")
        self._prev_sim = os.environ.get("SAPPHIRE_SIMULATE_MODELS")
        os.environ["SAPPHIRE_MOAT_DB"] = self._db
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"  # stub personas; rescue-mechanism is exempt

    def tearDown(self):
        os.unlink(self._db)
        for k, v in (("SAPPHIRE_MOAT_DB", self._prev_db),
                     ("SAPPHIRE_SIMULATE_MODELS", self._prev_sim)):
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _ctx(self):
        from emet.session_bridge import make_session_emet_handler
        # No envelope ⇒ EMET abstains honestly (login_required); the test exercises the moat +
        # mechanism + ranked-synthesis path, not EMET content. A mock runner stands in for claude.
        return {"runner": _mock_runner_factory(),
                "emet_handler": make_session_emet_handler({})}


class TestRescueRankingDeliverable(_Base):
    def test_produces_discovery_candidates_for_global_hits(self):
        """When no queried-gene list is provided, global top hits go to discovery_candidates.

        Query = 'Rank genes that rescue the TSC2-KO phenotype' (TSC2 only → target=TSC2).
        All global rescue hits (DCTN6/FZD7/RALA) must go into discovery_candidates;
        ranked_genes has no rescue_candidate entries (no candidates to rank).
        """
        from live_engine import run_live
        q = ("Rank genes that rescue the TSC2-K/O phenotype based on Quiver data and supporting "
             "evidence / plausible mechanistic explanations from the literature.")
        res = run_live(q, ctx=self._ctx())
        syn = res["synthesize"]
        # With no explicit candidate list, ranked_genes should have no rescue_candidates.
        ranked = syn.get("ranked_genes", [])
        rescue_candidates = [g for g in ranked if g.get("role") == "rescue_candidate"]
        self.assertEqual(rescue_candidates, [],
                         "No queried candidates → no rescue_candidate rows in ranked_genes")
        # Global top hits go to discovery_candidates.
        disc = syn.get("discovery_candidates")
        self.assertIsInstance(disc, list, "discovery_candidates must be a list")
        disc_names = {g["gene"] for g in disc}
        self.assertIn("DCTN6", disc_names, "DCTN6 = global top hit → discovery_candidates")
        self.assertIn("FZD7",  disc_names, "FZD7 = global top hit → discovery_candidates")
        self.assertIn("RALA",  disc_names, "RALA = global top hit → discovery_candidates")
        for entry in disc:
            self.assertEqual(entry["role"], "discovery_alpha")

    def test_produces_ranked_genes_with_queried_genes_ctx(self):
        """When ctx['queried_genes'] contains BCL2/CDK9, they appear in ranked_genes.

        BCL2 and CDK9 are in the moat fixture as rescue genes (opposite). The patched
        moat agent returns per-gene facts for them; ctx['queried_genes'] tells the
        synthesis block which genes the user is asking about.
        """
        import live_engine as _le
        from emet.session_bridge import make_session_emet_handler

        _original = _le._build_moat_agent

        def _patched():
            def _agent(inputs):
                from moat.facts import moat_facts
                # Emit global rescue facts + per-gene facts for BCL2/CDK9.
                global_rows = moat_facts("TSC2", k=6)
                facts = [
                    {"value": r["value"], "source": r["source"],
                     "tier": r["tier"], "provenance": r.get("provenance", "moat-real")}
                    for r in global_rows
                ]
                # Inject per-gene facts (simulating the per-gene moat fix output).
                # Note: "field" key is omitted — the harness findings schema has
                # additionalProperties:false so extra keys cause malformed-output. The
                # value string itself identifies these as per-gene facts.
                facts.insert(0, {
                    "value": "Queried rescue candidate: BCL2 opposes TSC2 KO EP-signature (union_rank 15, cos 0.112) [Quiver CNS_DFP]",
                    "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real",
                })
                facts.insert(1, {
                    "value": "Queried rescue candidate: CDK9 opposes TSC2 KO EP-signature (union_rank 19, cos 0.098) [Quiver CNS_DFP]",
                    "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real",
                })
                return {"candidate": "TSC2", "facts": facts, "provenance": "moat-real"}
            return _agent

        _le._build_moat_agent = _patched
        try:
            ctx = {
                "runner": _mock_runner_factory(),
                "emet_handler": make_session_emet_handler({}),
                "queried_genes": ["BCL2", "CDK9"],
            }
            res = _le.run_live("Rank genes that rescue the TSC2 KO phenotype.", ctx=ctx)
        finally:
            _le._build_moat_agent = _original

        syn = res["synthesize"]
        ranked = syn.get("ranked_genes", [])
        rescue = [g for g in ranked if g.get("role") == "rescue_candidate"]
        names = {g["gene"] for g in rescue}
        self.assertIn("BCL2", names, "BCL2 queried + in moat rescue → rescue_candidate")
        self.assertIn("CDK9", names, "CDK9 queried + in moat rescue → rescue_candidate")
        # DCTN6 not queried → must be in discovery_candidates, not ranked_genes
        ranked_names = {g["gene"] for g in ranked}
        self.assertNotIn("DCTN6", ranked_names)

    def test_discovery_candidates_holds_global_hits_not_in_queried_ctx(self):
        """discovery_candidates = global hits NOT in ctx['queried_genes']."""
        import live_engine as _le
        from emet.session_bridge import make_session_emet_handler

        _original = _le._build_moat_agent

        def _patched():
            def _agent(inputs):
                from moat.facts import moat_facts
                return {"candidate": "TSC2",
                        "facts": [{"value": r["value"], "source": r["source"],
                                   "tier": r["tier"], "provenance": r.get("provenance", "moat-real")}
                                  for r in moat_facts("TSC2", k=6)],
                        "provenance": "moat-real"}
            return _agent

        _le._build_moat_agent = _patched
        try:
            ctx = {
                "runner": _mock_runner_factory(),
                "emet_handler": make_session_emet_handler({}),
                # Only BCL2 queried — DCTN6/FZD7/RALA go to discovery_candidates.
                "queried_genes": ["BCL2"],
            }
            res = _le.run_live("Rank genes that rescue the TSC2 KO phenotype.", ctx=ctx)
        finally:
            _le._build_moat_agent = _original

        disc = res["synthesize"].get("discovery_candidates", [])
        disc_names = {g["gene"] for g in disc}
        self.assertIn("DCTN6", disc_names, "DCTN6 not queried → discovery_candidates")
        self.assertIn("FZD7",  disc_names, "FZD7 not queried → discovery_candidates")
        self.assertIn("RALA",  disc_names, "RALA not queried → discovery_candidates")
        self.assertNotIn("BCL2", disc_names, "BCL2 queried → not in discovery_candidates")
        for entry in disc:
            self.assertEqual(entry["role"], "discovery_alpha")

    def test_ranked_genes_ordered_by_ep_rank(self):
        """rescue_candidate entries in ranked_genes are sorted by union_rank ascending."""
        import live_engine as _le
        from emet.session_bridge import make_session_emet_handler

        _original = _le._build_moat_agent

        def _patched():
            def _agent(inputs):
                from moat.facts import moat_facts
                facts = [
                    {"value": r["value"], "source": r["source"],
                     "tier": r["tier"], "provenance": r.get("provenance", "moat-real")}
                    for r in moat_facts("TSC2", k=6)
                ]
                # FZD7 rank4 < BCL2 rank15; no "field" key (harness schema rejects it)
                for gene, rank, cos in [("FZD7", 4, 0.204), ("BCL2", 15, 0.112)]:
                    facts.insert(0, {
                        "value": f"Queried rescue candidate: {gene} opposes TSC2 KO EP-signature (union_rank {rank}, cos {cos}) [Quiver CNS_DFP]",
                        "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real",
                    })
                return {"candidate": "TSC2", "facts": facts, "provenance": "moat-real"}
            return _agent

        _le._build_moat_agent = _patched
        try:
            ctx = {
                "runner": _mock_runner_factory(),
                "emet_handler": make_session_emet_handler({}),
                "queried_genes": ["FZD7", "BCL2"],
            }
            res = _le.run_live("Rank genes that rescue the TSC2 KO phenotype.", ctx=ctx)
        finally:
            _le._build_moat_agent = _original

        rescue = [g for g in res["synthesize"].get("ranked_genes", [])
                  if g.get("role") == "rescue_candidate"]
        ranks = [g["rank"] for g in rescue]
        self.assertEqual(ranks, sorted(ranks), "rescue_candidates must be sorted by union_rank asc")
        # FZD7 (rank4) must precede BCL2 (rank15)
        names = [g["gene"] for g in rescue]
        self.assertLess(names.index("FZD7"), names.index("BCL2"))

    def test_queried_genes_carry_cited_mechanism(self):
        """rescue_candidate entries carry mechanism + citations from the rescue-mechanism reasoner."""
        import live_engine as _le
        from emet.session_bridge import make_session_emet_handler

        _original = _le._build_moat_agent

        def _patched():
            def _agent(inputs):
                from moat.facts import moat_facts
                facts = [{"value": r["value"], "source": r["source"],
                          "tier": r["tier"], "provenance": r.get("provenance", "moat-real")}
                         for r in moat_facts("TSC2", k=6)]
                # no "field" key — harness schema strips it
                facts.insert(0, {
                    "value": "Queried rescue candidate: BCL2 opposes TSC2 KO EP-signature (union_rank 15, cos 0.112) [Quiver CNS_DFP]",
                    "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real",
                })
                return {"candidate": "TSC2", "facts": facts, "provenance": "moat-real"}
            return _agent

        _le._build_moat_agent = _patched
        try:
            ctx = {
                "runner": _mock_runner_factory(),
                "emet_handler": make_session_emet_handler({}),
                "queried_genes": ["BCL2"],
            }
            res = _le.run_live("Rank genes that rescue the TSC2 KO phenotype.", ctx=ctx)
        finally:
            _le._build_moat_agent = _original

        ranked = {g["gene"]: g for g in res["synthesize"].get("ranked_genes", [])
                  if g.get("role") == "rescue_candidate"}
        self.assertIn("BCL2", ranked, "BCL2 queried + in moat rescue → rescue_candidate")
        self.assertEqual(ranked["BCL2"]["citations"], ["PMID:34567890"])
        self.assertIn("autophagy", ranked["BCL2"]["mechanism"])

    def test_recommendation_mentions_queried_rescue_gene(self):
        """Recommendation uses queried rescue candidates when ctx['queried_genes'] is set."""
        import live_engine as _le
        from emet.session_bridge import make_session_emet_handler

        _original = _le._build_moat_agent

        def _patched():
            def _agent(inputs):
                from moat.facts import moat_facts
                facts = [{"value": r["value"], "source": r["source"],
                          "tier": r["tier"], "provenance": r.get("provenance", "moat-real")}
                         for r in moat_facts("TSC2", k=6)]
                # no "field" key — harness schema rejects additional properties
                facts.insert(0, {
                    "value": "Queried rescue candidate: BCL2 opposes TSC2 KO EP-signature (union_rank 15, cos 0.112) [Quiver CNS_DFP]",
                    "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real",
                })
                return {"candidate": "TSC2", "facts": facts, "provenance": "moat-real"}
            return _agent

        _le._build_moat_agent = _patched
        try:
            ctx = {
                "runner": _mock_runner_factory(),
                "emet_handler": make_session_emet_handler({}),
                "queried_genes": ["BCL2"],
            }
            res = _le.run_live("Rank genes that rescue the TSC2 KO phenotype.", ctx=ctx)
        finally:
            _le._build_moat_agent = _original

        rec = res["synthesize"]["recommendation"]
        self.assertIn("rescue", rec.lower())
        self.assertIn("BCL2", rec, f"Recommendation must mention queried BCL2; got: {rec!r}")

    def test_mechanism_agent_runs_real_not_simulated(self):
        from live_engine import run_live
        res = run_live("rank genes that rescue the TSC2 KO phenotype", ctx=self._ctx())
        statuses = {a["id"]: a for a in res["discover"]["agents"]}
        self.assertIn("rescue-mechanism", statuses)
        self.assertEqual(statuses["rescue-mechanism"]["status"], "ok")
        # HONESTY: real reasoning keeps its genuine provenance even under the global simulate flag
        self.assertEqual(statuses["rescue-mechanism"]["provenance"], "scientific-reasoning")

    def test_mechanism_step_streams(self):
        from live_engine import run_live
        events = []
        run_live("rank genes that rescue the TSC2 KO phenotype",
                 ctx=self._ctx(), on_progress=events.append)
        steps = [e for e in events if e.get("agent_id") == "rescue-mechanism"]
        phases = {e.get("phase") for e in steps}
        self.assertEqual(phases, {"start", "done"})

    def test_uncited_high_confidence_downgraded_to_low(self):
        """HONESTY (cite-or-hedge): an uncited high/medium claim is forced to low by the engine,
        so a confident-but-unsupported mechanism is never presented as well-grounded.
        Uses ctx['queried_genes'] = ['BCL2', 'FZD7'] so both surface in ranked_genes."""
        import json
        import live_engine as _le
        from emet.session_bridge import make_session_emet_handler

        body = {"target": "TSC2", "provenance": "scientific-reasoning", "gene_mechanisms": [
            # high confidence but NO citations — must be downgraded
            {"gene": "BCL2", "rank": 1, "mechanism": "Confident but uncited mTORC1 claim.",
             "citations": [], "confidence": "high"},
            # medium with a citation — must be preserved
            {"gene": "FZD7", "rank": 2, "mechanism": "Cited Wnt/mTORC1 claim.",
             "citations": ["PMID:99"], "confidence": "medium"}]}

        class _Proc:
            returncode = 0
            stderr = ""
            stdout = json.dumps({"structured_output": body})

        _original = _le._build_moat_agent

        def _patched():
            def _agent(inputs):
                from moat.facts import moat_facts
                facts = [{"value": r["value"], "source": r["source"],
                          "tier": r["tier"], "provenance": r.get("provenance", "moat-real")}
                         for r in moat_facts("TSC2", k=6)]
                # no "field" key — harness schema rejects additional properties
                for gene, rank, cos in [("BCL2", 15, 0.112), ("FZD7", 4, 0.204)]:
                    facts.insert(0, {
                        "value": f"Queried rescue candidate: {gene} opposes TSC2 KO EP-signature (union_rank {rank}, cos {cos}) [Quiver CNS_DFP]",
                        "source": "Quiver CNS_DFP", "tier": "T2", "provenance": "moat-real",
                    })
                return {"candidate": "TSC2", "facts": facts, "provenance": "moat-real"}
            return _agent

        _le._build_moat_agent = _patched
        try:
            ctx = {
                "runner": lambda cmd: _Proc(),
                "emet_handler": make_session_emet_handler({}),
                "queried_genes": ["BCL2", "FZD7"],
            }
            res = _le.run_live("Rank genes that rescue the TSC2 KO phenotype.", ctx=ctx)
        finally:
            _le._build_moat_agent = _original

        rescue = {g["gene"]: g for g in res["synthesize"].get("ranked_genes", [])
                  if g.get("role") == "rescue_candidate"}
        self.assertIn("BCL2", rescue, "BCL2 queried + in moat rescue → must be in ranked_genes")
        self.assertIn("FZD7", rescue, "FZD7 queried + in moat rescue → must be in ranked_genes")
        self.assertEqual(rescue["BCL2"]["confidence"], "low")    # uncited high → low
        self.assertEqual(rescue["FZD7"]["confidence"], "medium")  # cited medium preserved

    def test_mechanism_facts_in_dossier(self):
        from live_engine import run_live
        res = run_live("rank genes that rescue the TSC2 KO phenotype", ctx=self._ctx())
        mech = [f for f in res["discover"]["dossier"]
                if f.get("provenance") == "scientific-reasoning"]
        self.assertGreaterEqual(len(mech), 2)
        for f in mech:
            self.assertEqual(f.get("plane"), "external")  # public reasoning, never internal


class TestNonRescueQueryUnchanged(_Base):
    def test_viability_query_has_no_ranked_genes(self):
        from live_engine import run_live
        res = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=self._ctx())
        self.assertNotIn("ranked_genes", res["synthesize"])
        # and no rescue-mechanism agent ran
        ids = {a["id"] for a in res["discover"]["agents"]}
        self.assertNotIn("rescue-mechanism", ids)


class TestIntentDetection(unittest.TestCase):
    def test_matches_rescue_ranking(self):
        from live_engine import _is_rescue_ranking_query
        self.assertTrue(_is_rescue_ranking_query(
            "Rank genes that rescue the TSC2-K/O phenotype based on Quiver data"))
        self.assertTrue(_is_rescue_ranking_query("identify genes that rescue the SCN2A knockdown signature"))

    def test_rejects_ordinary_queries(self):
        from live_engine import _is_rescue_ranking_query
        self.assertFalse(_is_rescue_ranking_query("Is TSC2 a viable target in tuberous sclerosis?"))
        self.assertFalse(_is_rescue_ranking_query("What is the safety profile of rapamycin?"))
        # "rescue" alone, without a gene+KO cue, does not trigger the deliverable
        self.assertFalse(_is_rescue_ranking_query("Can this drug rescue patients?"))

    def test_rejects_compound_ranking(self):
        # a rescue-COMPOUND ranking question is a different deliverable — must NOT hit the gene path
        from live_engine import _is_rescue_ranking_query
        self.assertFalse(_is_rescue_ranking_query(
            "rank the rescue compound candidates for the TSC2 knockout signature"))
        self.assertFalse(_is_rescue_ranking_query(
            "which small-molecule rescue drugs reverse the TSC2 KO phenotype?"))


if __name__ == "__main__":
    unittest.main()
