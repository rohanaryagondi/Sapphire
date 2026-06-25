"""Integration: the rescue-gene-ranking deliverable in run_live.

A "rank genes that rescue the TSC2-KO phenotype" query must:
  - detect the rescue-ranking intent,
  - pull the moat's OPPOSITE genes (the rescuers) as the ranked candidates,
  - run the simulate_exempt rescue-mechanism reasoner (REAL even under simulate; here a mock
    runner stands in for `claude -p` so CI never shells out),
  - emit a `synthesize.ranked_genes` table merging moat rank + cited mechanism,
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
    con.execute("""CREATE TABLE neighbors (query TEXT, query_type TEXT, ref TEXT, ref_type TEXT,
                   ref_dose TEXT, effect TEXT, rank INTEGER, cosine REAL, euclidean REAL)""")
    con.execute("CREATE TABLE moat_meta (key TEXT PRIMARY KEY, value TEXT)")
    rows = [
        ("TSC2", "gene", "TSC1",  "gene", None, "similar",  1, 0.970, 0.18),
        # the rescuers — opposite-signature genes, rank-ordered
        ("TSC2", "gene", "DCTN6", "gene", None, "opposite", 1, 0.163, 0.50),
        ("TSC2", "gene", "FZD7",  "gene", None, "opposite", 2, 0.204, 0.55),
        ("TSC2", "gene", "RALA",  "gene", None, "opposite", 3, 0.227, 0.60),
        ("TSC2", "gene", "RAPAMYCIN", "compound", "10nM", "opposite", 1, 0.823, 0.44),
    ]
    con.executemany("INSERT INTO neighbors VALUES (?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return db


def _mock_runner_factory():
    """A runner standing in for the rescue-mechanism `claude -p` call."""
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
    def test_produces_ranked_genes(self):
        from live_engine import run_live
        q = ("Rank genes that rescue the TSC2-K/O phenotype based on Quiver data and supporting "
             "evidence / plausible mechanistic explanations from the literature.")
        res = run_live(q, ctx=self._ctx())
        ranked = res["synthesize"].get("ranked_genes")
        self.assertIsInstance(ranked, list)
        self.assertGreaterEqual(len(ranked), 3)
        genes = [g["gene"] for g in ranked]
        # the moat rescuers (opposite genes), in rank order — NOT the similar gene / compound
        self.assertEqual(genes[:3], ["DCTN6", "FZD7", "RALA"])
        self.assertNotIn("TSC1", genes)
        self.assertNotIn("RAPAMYCIN", genes)

    def test_top_genes_carry_cited_mechanism(self):
        from live_engine import run_live
        res = run_live("rank the genes that rescue the TSC2 KO phenotype", ctx=self._ctx())
        ranked = {g["gene"]: g for g in res["synthesize"]["ranked_genes"]}
        self.assertEqual(ranked["DCTN6"]["confidence"], "high")
        self.assertEqual(ranked["DCTN6"]["citations"], ["PMID:12345678"])
        self.assertIn("mTORC1", ranked["DCTN6"]["mechanism"])

    def test_recommendation_is_a_ranked_summary(self):
        from live_engine import run_live
        res = run_live("rank genes that rescue the TSC2 knockout phenotype", ctx=self._ctx())
        rec = res["synthesize"]["recommendation"]
        self.assertIn("rescue-gene", rec.lower())
        self.assertIn("DCTN6", rec)

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
        so a confident-but-unsupported mechanism is never presented as well-grounded."""
        import json
        from emet.session_bridge import make_session_emet_handler
        from live_engine import run_live

        body = {"target": "TSC2", "provenance": "scientific-reasoning", "gene_mechanisms": [
            # high confidence but NO citations — must be downgraded
            {"gene": "DCTN6", "rank": 1, "mechanism": "Confident but uncited mTORC1 claim.",
             "citations": [], "confidence": "high"},
            # medium with a citation — must be preserved
            {"gene": "FZD7", "rank": 2, "mechanism": "Cited Wnt/mTORC1 claim.",
             "citations": ["PMID:99"], "confidence": "medium"}]}

        class _Proc:
            returncode = 0
            stderr = ""
            stdout = json.dumps({"structured_output": body})

        ctx = {"runner": lambda cmd: _Proc(),
               "emet_handler": make_session_emet_handler({})}
        res = run_live("rank genes that rescue the TSC2 KO phenotype", ctx=ctx)
        ranked = {g["gene"]: g for g in res["synthesize"]["ranked_genes"]}
        self.assertEqual(ranked["DCTN6"]["confidence"], "low")   # uncited high → low
        self.assertEqual(ranked["FZD7"]["confidence"], "medium")  # cited medium preserved

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


class TestRescueEvidenceEnvelope(unittest.TestCase):
    """_load_rescue_evidence: a dedicated gene-specific rescue envelope feeds the reasoner;
    its absence degrades to [] (the caller then falls back to the general dossier facts)."""

    def test_loads_and_normalizes_rescue_envelope(self):
        from unittest import mock
        import live_engine
        fake = {"candidate": "TSC2_rescue", "evidence": [
            {"claim": "DCTN6 modulates dynein-mediated mTORC1 lysosomal positioning.", "id_or_url": "PMID:111"},
            {"claim": "FZD7/Wnt cross-talks with mTORC1.", "source": "PMID:222"},
            {"value": "", "id_or_url": "PMID:333"},  # empty claim dropped
        ]}
        with mock.patch("emet.envelopes.load_envelope_for", return_value=fake):
            ev = live_engine._load_rescue_evidence("TSC2")
        self.assertEqual(len(ev), 2)  # the empty-claim row is dropped
        self.assertEqual(ev[0], {"claim": "DCTN6 modulates dynein-mediated mTORC1 lysosomal positioning.",
                                 "source": "PMID:111"})
        self.assertEqual(ev[1]["source"], "PMID:222")

    def test_absent_envelope_returns_empty(self):
        from unittest import mock
        import live_engine
        with mock.patch("emet.envelopes.load_envelope_for", return_value=None):
            self.assertEqual(live_engine._load_rescue_evidence("TSC2"), [])

    def test_never_raises(self):
        from unittest import mock
        import live_engine
        with mock.patch("emet.envelopes.load_envelope_for", side_effect=RuntimeError("boom")):
            self.assertEqual(live_engine._load_rescue_evidence("TSC2"), [])


if __name__ == "__main__":
    unittest.main()
