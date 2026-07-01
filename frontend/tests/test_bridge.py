"""Offline tests for frontend/bridge.py — the in-process run_live seam.

Uses mock=True (the offline mock ctx), so $0, no network, deterministic. Isolates
engagement/memory writes to temp dirs.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_FRONTEND = Path(__file__).resolve().parents[1]
_ENGINE = _FRONTEND.parent / "sapphire-orchestrator"
for p in (str(_FRONTEND), str(_ENGINE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import bridge  # noqa: E402
from contracts.run_live_schema import validate_run_live  # noqa: E402


class TestBridge(unittest.TestCase):
    def setUp(self):
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_run_mock_conforms_to_contract(self):
        r = bridge.run("Is TSC2 a viable target in tuberous sclerosis?", mock=True)
        # validate_run_live ignores additive keys (_elapsed_s, _mock) — additive contract.
        self.assertEqual(validate_run_live(r), [])
        self.assertIn("_elapsed_s", r)
        self.assertTrue(r["_mock"])
        self.assertEqual(r["_via"], "harness-live")

    def test_simulate_models_labels_personas_keeps_facts_real(self):
        import sys, os as _os
        _orch = _os.path.join(_os.path.dirname(__file__), '..', '..', 'sapphire-orchestrator')
        if _orch not in sys.path:
            sys.path.insert(0, _orch)
        from moat.client import MoatClient
        from moat.facts import moat_facts as _moat_facts
        # Skip if the moat DB is unavailable or has no TSC2 hits.
        if not MoatClient().available() or not _moat_facts("TSC2", k=1):
            self.skipTest("moat DB unavailable or no TSC2 hits — skipping moat-real provenance assertion")
        r = bridge.run("Is TSC2 a viable target in tuberous sclerosis?", mock=True, simulate=True)
        self.assertEqual(validate_run_live(r), [])           # still a valid run
        self.assertTrue(r["_simulated"])
        # personas are SIMULATED + clearly labeled (provenance + 🧪 marker)
        verdicts = r["consult"]["round1"]
        self.assertTrue(verdicts)
        self.assertEqual(verdicts[0]["provenance"], "simulated")
        self.assertIn("🧪", verdicts[0]["rationale"])
        # real backends (mock ctx here) still carry their REAL provenance — moat stays moat-real
        provs = {f.get("provenance") for f in r["discover"]["dossier"]}
        self.assertIn("moat-real", provs)

    def test_no_simulate_by_default_and_env_restored(self):
        r = bridge.run("Is TSC2 a viable target in tuberous sclerosis?", mock=True)
        self.assertFalse(r.get("_simulated"))
        self.assertNotIn("SAPPHIRE_SIMULATE_MODELS", os.environ)   # env restored — no leak

    def test_on_progress_forwarded_to_run_live(self):
        events = []
        r = bridge.run("Is TSC2 a viable target in tuberous sclerosis?", mock=True,
                       on_progress=events.append)
        self.assertEqual(validate_run_live(r), [])      # still a valid run
        self.assertTrue(events, "bridge.run must forward on_progress to run_live")
        stages = {e["stage"] for e in events}
        # WO-9 Phase 2: a "report" stage is now always emitted (a terminal "done" event,
        # plus "chunk" events whenever the report synthesizer produced streamable text).
        self.assertEqual(stages, {"plan", "bucket1", "flags", "roundtable", "synthesis", "report"})
        self.assertEqual(events[0]["stage"], "plan")
        report_phases = {e["phase"] for e in events if e["stage"] == "report"}
        self.assertIn("done", report_phases, "the report stage must always emit a terminal 'done' event")

    def test_empty_query_does_not_crash(self):
        # An empty query never raises. The engine treats it as a general-CNS run (not a
        # degraded/zero-fact result), so assert the contract-valid shape + that the firm
        # really ran (_via harness-live, not a bridge error) — not a vacuous "is a dict".
        r = bridge.run("", mock=True)
        self.assertEqual(validate_run_live(r), [])
        self.assertEqual(r["_via"], "harness-live")

    def test_sequences_forwarded_to_run_live(self):
        # The bridge must accept and forward `sequences` (the ASO-Design handoff), not drop it.
        captured = {}
        import live_engine
        orig = live_engine.run_live

        def _spy(query, *, sequences=None, ctx=None, **kw):
            captured["sequences"] = sequences
            return orig(query, sequences=sequences, ctx=ctx, **kw)

        live_engine.run_live = _spy
        try:
            r = bridge.run("screen this ASO", mock=True, sequences=["GCACTTGAATTTCACGTTGT"])
        finally:
            live_engine.run_live = orig
        self.assertEqual(captured["sequences"], ["GCACTTGAATTTCACGTTGT"])
        self.assertEqual(validate_run_live(r), [])

    def test_model_sets_claude_model_env_during_run_and_restores(self):
        # The cheap-live lever: `model` must be visible to dispatch_claude (via CLAUDE_MODEL)
        # DURING the run, and restored afterwards.
        import os
        import live_engine
        seen = {}
        orig = live_engine.run_live

        def _spy(query, *, sequences=None, ctx=None, **kw):
            seen["during"] = os.environ.get("CLAUDE_MODEL")
            return orig(query, sequences=sequences, ctx=ctx, **kw)

        prev = os.environ.pop("CLAUDE_MODEL", None)
        live_engine.run_live = _spy
        try:
            r = bridge.run("q", mock=True, model="claude-haiku-4-5")
        finally:
            live_engine.run_live = orig
            if prev is not None:
                os.environ["CLAUDE_MODEL"] = prev
        self.assertEqual(seen["during"], "claude-haiku-4-5")          # set during the run
        self.assertEqual(r["_model"], "claude-haiku-4-5")             # echoed on the result
        self.assertIsNone(os.environ.get("CLAUDE_MODEL"))             # restored (was unset) after

    def test_no_model_leaves_env_untouched(self):
        import os
        prev = os.environ.pop("CLAUDE_MODEL", None)
        try:
            r = bridge.run("q", mock=True)
            self.assertIsNone(os.environ.get("CLAUDE_MODEL"))
            self.assertEqual(r["_model"], "")
        finally:
            if prev is not None:
                os.environ["CLAUDE_MODEL"] = prev

    def test_build_ctx_live_is_none(self):
        self.assertIsNone(bridge.build_ctx(False))
        self.assertIsInstance(bridge.build_ctx(True), dict)

    def test_bridge_error_envelope_is_wellformed(self):
        env = bridge._error_envelope("q", RuntimeError("boom"))
        self.assertEqual(validate_run_live(env), [])
        self.assertEqual(env["_via"], "bridge-error")
        self.assertIn("boom", env["discover"]["flags"]["KNOWN_UNKNOWNS"][0])


# A captured TSC2 EMET envelope (the session-bridge shape) — real PMIDs, public ids only. Used to
# exercise the injection path HTTP-free (no live browser): the session handler stands in for what
# the orchestrator captures from its authenticated session.
_TSC2_ENV = {
    "candidate": "TSC2", "emet_workflow": "Target Validation", "verdict": "pass",
    "evidence": [
        {"claim": "TSC1/TSC2 is the GAP for Rheb; loss → constitutive mTORC1.",
         "source": "Han & Sahin, FEBS Lett 2011", "id_or_url": "PMID:21329690"},
        {"claim": "mTOR inhibition (everolimus) reduces SEGA volume in TSC.",
         "source": "Ichikawa & Niida 2022", "id_or_url": "PMID:35169091"},
    ],
    "notes": "", "chat_url": "https://emet.benchsci.com/chat/c4a1031a",
    "captured_at": "2026-06-25T17:12:00Z", "provenance": "emet-live",
}


class TestBridgeEmetSession(unittest.TestCase):
    """The front end's real-EMET path: an injected/auto-loaded captured envelope lands real
    emet-live PMIDs for a covered candidate; an uncovered candidate abstains honestly. HTTP-free
    (mock ctx + captured envelope) — the session handler replaces the mock EMET handler."""

    def setUp(self):
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_explicit_envelopes_land_emet_live_facts(self):
        import re
        r = bridge.run("Is TSC2 a viable target in tuberous sclerosis?", mock=True,
                       emet_envelopes={"TSC2": _TSC2_ENV})
        self.assertEqual(validate_run_live(r), [])
        emet = [f for f in r["discover"]["dossier"] if f.get("provenance") == "emet-live"]
        pmids = sorted({m for f in emet for m in re.findall(r"PMID:\d+", f.get("source", ""))})
        self.assertIn("PMID:21329690", pmids)            # the REAL PMID, not fabricated
        self.assertEqual(r["_emet_session"], ["TSC2"])   # labeled: ran via the session path
        agents = {a["id"]: a["status"] for a in r["discover"]["agents"]}
        self.assertEqual(agents.get("emet-runner"), "ok")

    def test_uncovered_candidate_abstains_not_fabricates(self):
        # An explicit envelope dict that does NOT cover the run's candidate → session handler
        # abstains honestly for KCNT1; no emet-live facts are fabricated.
        r = bridge.run("Is KCNT1 a viable target?", mock=True,
                       emet_envelopes={"TSC2": _TSC2_ENV})
        emet = [f for f in r["discover"]["dossier"] if f.get("provenance") == "emet-live"]
        self.assertEqual(emet, [])                       # nothing fabricated
        agents = {a["id"]: a["status"] for a in r["discover"]["agents"]}
        self.assertIn(agents.get("emet-runner"), ("abstained", "escalated"))

    def test_empty_envelopes_uses_default_handler_not_session(self):
        # emet_envelopes={} (explicit, no auto-load) → the session handler is NOT wired; the mock
        # ctx's own EMET handler runs. _emet_session stays empty (honest: no covered candidate).
        r = bridge.run("Is TSC2 a viable target in tuberous sclerosis?", mock=True,
                       emet_envelopes={})
        self.assertEqual(validate_run_live(r), [])
        self.assertEqual(r["_emet_session"], [])

    def test_auto_load_resolves_shipped_tsc2_envelope(self):
        # With emet_envelopes=None, the bridge AUTO-LOADS the shipped tsc2.json for the run's
        # candidate. Assert the resolver finds it (the run itself is exercised in the engine test
        # against run_live; here we pin the resolver wiring without a model call).
        envs = bridge._resolve_emet_envelopes("Is TSC2 a viable target?", None)
        self.assertIn("TSC2", envs)
        self.assertEqual(envs["TSC2"]["provenance"], "emet-live")
        self.assertEqual(len(envs["TSC2"]["evidence"]), 24)  # the 24 shipped citations (14 PMIDs + 10 DOIs)

    def test_auto_load_uncovered_candidate_resolves_empty(self):
        self.assertEqual(bridge._resolve_emet_envelopes("Is KCNT1 a target?", None), {})

    def test_candidate_extraction(self):
        self.assertEqual(bridge._candidate_of("Is TSC2 a viable target?"), "TSC2")
        self.assertEqual(bridge._candidate_of(""), "")


if __name__ == "__main__":
    unittest.main()
