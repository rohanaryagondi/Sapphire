"""Offline tests for the robyn_scs Bucket-1 seam — no subprocess, no heavy deps.

Honest-empty when no imaging data; summarised facts when the (mocked) pipeline returns a result;
honest KNOWN_UNKNOWN on error — never a fabricated connectivity result.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sapphire-orchestrator/
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)

from tools import robyn_scs_seam as seam  # noqa: E402
from contracts.provenance import is_valid_provenance, plane_for  # noqa: E402


def _ok_runner(summary):
    return lambda req_json: json.dumps({"ok": True, "summary": summary})


class TestRobynScsSeam(unittest.TestCase):

    def test_honest_empty_when_no_imaging_data(self):
        out = seam.findings({"candidate": "TSC2", "disease": "tuberous sclerosis"})
        self.assertEqual(out["facts"], [])
        self.assertEqual(out["provenance"], "robyn-scs")
        self.assertEqual(out["candidate"], "TSC2")

    def test_fires_when_robyn_scs_input_present(self):
        summary = {"n_fovs": 3, "n_quartets": 4, "n_connections": 42, "n_neurons": 88,
                   "tiers": {"tier1": 10, "tier2": 32}, "failed": []}
        out = seam.findings({"candidate": "SCN2A", "robyn_scs": {"input_dir": "/plate/v17_traces"}},
                            runner=_ok_runner(summary))
        self.assertTrue(out["facts"])
        v = out["facts"][0]["value"]
        self.assertIn("42 tiered connection", v)
        self.assertIn("88 classified neuron", v)
        self.assertEqual(out["facts"][0]["tier"], "T2")

    def test_string_input_dir_accepted(self):
        out = seam.findings({"candidate": "X", "robyn_scs": "/plate/v17_traces"},
                            runner=_ok_runner({"n_connections": 1, "n_fovs": 1, "n_neurons": 2,
                                               "tiers": {}, "failed": []}))
        self.assertTrue(out["facts"])

    def test_failed_fovs_surface_as_known_unknown(self):
        summary = {"n_fovs": 2, "n_connections": 5, "n_neurons": 10, "tiers": {},
                   "failed": ["FOV_0007"]}
        out = seam.findings({"candidate": "X", "robyn_scs": {"input_dir": "/p"}},
                            runner=_ok_runner(summary))
        flags = [f.get("flag") for f in out["facts"]]
        self.assertIn("KNOWN_UNKNOWN", flags)

    def test_pipeline_error_is_known_unknown_not_fabricated(self):
        out = seam.findings({"candidate": "X", "robyn_scs": {"input_dir": "/p"}},
                            runner=lambda r: json.dumps({"ok": False, "error": "no FOVs found"}))
        self.assertEqual(out["facts"][0]["flag"], "KNOWN_UNKNOWN")
        self.assertIn("no FOVs found", out["facts"][0]["value"])

    def test_runner_exception_is_honest(self):
        def _boom(r):
            raise RuntimeError("subprocess died")
        out = seam.findings({"candidate": "X", "robyn_scs": {"input_dir": "/p"}}, runner=_boom)
        self.assertEqual(out["facts"][0]["flag"], "KNOWN_UNKNOWN")

    def test_provenance_internal_plane(self):
        self.assertTrue(is_valid_provenance("robyn-scs"))
        self.assertEqual(plane_for("robyn-scs"), "internal")  # imaging-derived internal data

    def test_empty_plate_real_subprocess_does_not_fabricate(self):
        # NON-mocked: exercises the real _default_runner → firm_endpoint.py on an EMPTY plate dir.
        # Whether the heavy deps import or not, the honest outcome is the same: NO fabricated
        # "0 connections" success fact — either honest-empty or a KNOWN_UNKNOWN. (Gate-5 defect repro.)
        with tempfile.TemporaryDirectory() as d:
            out = seam.findings({"candidate": "X", "robyn_scs": {"input_dir": d}})
        facts = out["facts"]
        if facts:
            self.assertEqual(facts[0].get("flag"), "KNOWN_UNKNOWN")
            self.assertNotIn("tiered connection", facts[0]["value"])  # never a success fact
        else:
            self.assertEqual(facts, [])


class TestRobynScsThroughRunLive(unittest.TestCase):
    """The robyn-scs agent is registered + fires honest-empty in a standard (no-imaging) run."""

    def setUp(self):
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()
        sys.path.insert(0, os.path.join(_PKG, "tests"))

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_agent_registered_and_honest_empty(self):
        """WO-9: robyn-scs is NOT selected for a standard gene query (no imaging data).
        It must NOT appear in discover.agents. No robyn-scs facts in the dossier."""
        from test_live_engine import _build_ctx
        from live_engine import run_live
        result = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=_build_ctx())
        agents = {a["id"]: a["status"] for a in result["discover"]["agents"]}
        # WO-9: robyn-scs must NOT appear in agents for a no-imaging query.
        self.assertNotIn("robyn-scs", agents,
                         "robyn-scs must NOT be in discover.agents for a query with no imaging data "
                         "(WO-9: skipped tools produce no trace noise)")
        # No robyn-scs facts in the dossier.
        rs = [f for f in result["discover"]["dossier"] if f.get("provenance") == "robyn-scs"]
        self.assertEqual(rs, [])


if __name__ == "__main__":
    unittest.main()
