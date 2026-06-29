"""Offline tests for the captured-EMET envelope store (emet/envelopes.py) and its auto-load
injection through run_live. No live browser, no network — the stored envelope stands in for what
the orchestrator captures from its authenticated session.

Proves: the shipped tsc2.json loads with its 9 real PMIDs; a covered candidate auto-loads + lands
emet-live facts via run_live; an uncovered candidate loads nothing (→ honest abstain); malformed
captures are skipped, never crash.
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

from emet.envelopes import load_envelopes, load_envelope_for, envelopes_dir
from emet.session_bridge import make_session_emet_handler

_SHIPPED = Path(__file__).resolve().parents[2] / "scenarios" / "emet_envelopes"


class TestEnvelopeStore(unittest.TestCase):

    def test_shipped_tsc2_envelope_loads_with_real_pmids(self):
        envs = load_envelopes(_SHIPPED)
        self.assertIn("TSC2", envs)
        env = envs["TSC2"]
        self.assertEqual(env["provenance"], "emet-live")
        ids = {e["id_or_url"] for e in env["evidence"]}
        self.assertEqual(len(ids), 24)                      # 24 real captured citations (14 PMIDs + 10 DOIs)
        self.assertIn("PMID:12172553", ids)                 # a real captured PMID (Inoki et al. 2002, Akt→TSC2)

    def test_load_envelope_for_is_case_tolerant(self):
        self.assertIsNotNone(load_envelope_for("TSC2", _SHIPPED))
        self.assertIsNotNone(load_envelope_for("tsc2", _SHIPPED))

    def test_uncovered_candidate_loads_none(self):
        self.assertIsNone(load_envelope_for("KCNT1", _SHIPPED))
        self.assertIsNone(load_envelope_for("", _SHIPPED))

    def test_missing_dir_returns_empty(self):
        self.assertEqual(load_envelopes(tempfile.mkdtemp() + "/nope"), {})

    def test_malformed_capture_is_skipped_not_crashed(self):
        d = tempfile.mkdtemp()
        (Path(d) / "bad.json").write_text("{ not json", encoding="utf-8")
        (Path(d) / "ok.json").write_text(
            json.dumps({"candidate": "X", "evidence": [], "provenance": "emet-live"}),
            encoding="utf-8")
        envs = load_envelopes(d)
        self.assertEqual(set(envs), {"X"})                  # bad skipped, good kept

    def test_env_override_dir(self):
        prev = os.environ.get("SAPPHIRE_EMET_ENVELOPES_DIR")
        os.environ["SAPPHIRE_EMET_ENVELOPES_DIR"] = str(_SHIPPED)
        try:
            self.assertEqual(envelopes_dir(), _SHIPPED)
        finally:
            if prev is None:
                os.environ.pop("SAPPHIRE_EMET_ENVELOPES_DIR", None)
            else:
                os.environ["SAPPHIRE_EMET_ENVELOPES_DIR"] = prev


class TestAutoLoadedEnvelopeThroughRunLive(unittest.TestCase):
    """The shipped tsc2.json, injected via the session handler, lands its real PMIDs in the
    dossier through run_live (offline mock ctx — HTTP-free, $0)."""

    def setUp(self):
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()
        _here = os.path.dirname(os.path.abspath(__file__))
        _pkg = os.path.dirname(os.path.dirname(_here))      # sapphire-orchestrator/
        for p in (_pkg, os.path.join(_pkg, "tests")):
            if p not in sys.path:
                sys.path.insert(0, p)

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_shipped_envelope_lands_real_pmids(self):
        from test_live_engine import _build_ctx
        from live_engine import run_live
        env = load_envelope_for("TSC2", _SHIPPED)
        ctx = _build_ctx()
        ctx["emet_handler"] = make_session_emet_handler({"TSC2": env})
        result = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=ctx)
        emet = [f for f in result["discover"]["dossier"]
                if f.get("provenance") == "emet-live"]
        pmids = sorted({m for f in emet for m in re.findall(r"PMID:\d+", f.get("source", ""))})
        self.assertEqual(len(pmids), 14)                    # all 14 real captured PMIDs land
        self.assertTrue(all(f.get("plane") == "external" for f in emet))
        agents = {a["id"]: a["status"] for a in result["discover"]["agents"]}
        self.assertEqual(agents.get("emet-runner"), "ok")


if __name__ == "__main__":
    unittest.main()
