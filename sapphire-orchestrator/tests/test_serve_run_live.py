"""Offline tests for the K1 service boundary: serve.route_api_run + the run_live
output contract.

No live server, no network, no claude CLI. The default route is proven to dispatch
to live_engine.run_live (monkeypatched) and stamp the honest `via` marker; a real
run_live (with mock backends) is proven to conform to the documented schema.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_serve_run_live -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(_HERE)
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import serve  # noqa: E402  (importing does NOT start a server — server is behind __main__)
from contracts.run_live_schema import validate_run_live  # noqa: E402


def _fake_run_live_result() -> dict:
    """A documented-shape run_live result (the field set serve must pass through)."""
    return {
        "query": "Is TSC2 a viable CNS target?",
        "plan": {"deliverable": "diligence", "disease": "tuberous sclerosis",
                 "modality": "small molecule", "agents": [], "panel": [],
                 "class": "diligence"},
        "priors": [],
        "discover": {
            "dossier": [{"value": "TSC2 loss activates mTOR", "source": "PMID:1",
                         "tier": "T2", "provenance": "emet-live"}],
            "flags": {"VETO": [], "DIVERGENCE": [], "KNOWN_UNKNOWNS": []},
            "status": "complete",
            "agents": [{"id": "emet-runner", "status": "ok", "provenance": "emet-live"}],
        },
        "consult": {
            "round1": [{"persona": "KOL", "stance": "conditional",
                        "provenance": "persona-judgment", "status": "ok"}],
            "round2": [],
            "spread": {"conviction_range": "3-3 / 5", "stance_mix": {"conditional": 1},
                       "moved_in_round2": [], "convergent_gate": ""},
        },
        "synthesize": {"recommendation": "Conditional advance", "confidence": "medium",
                       "proposed_experiment": "Run orthogonal validation.", "entities": {}},
        "engagement_id": "eng_test",
        "reflection": {"engagement_id": "eng_test", "written": 1, "records": []},
        "_via": "harness-live",
    }


class TestRouteApiRun(unittest.TestCase):

    def test_default_route_dispatches_to_run_live(self):
        """mode='live' (default) MUST call live_engine.run_live and stamp via=engine-live."""
        with mock.patch.object(serve.live_engine, "run_live",
                               return_value=_fake_run_live_result()) as m:
            out = serve.route_api_run("Is TSC2 a viable CNS target?", "live")
        m.assert_called_once()
        self.assertEqual(out["via"], "engine-live")
        self.assertTrue(out["live"])
        # The documented run_live keys flow through untouched.
        self.assertIn("discover", out)
        self.assertIn("dossier", out["discover"])
        self.assertEqual(out["engagement_id"], "eng_test")

    def test_default_route_output_conforms_to_contract(self):
        with mock.patch.object(serve.live_engine, "run_live",
                               return_value=_fake_run_live_result()):
            out = serve.route_api_run("Is TSC2 a viable CNS target?", "live")
        # via/live are additive stamps; the contract is additive-friendly → still valid.
        self.assertEqual(validate_run_live(out), [])

    def test_canned_mode_is_labeled_and_not_live(self):
        out = serve.route_api_run("Prioritize my Dravet syndrome targets", "canned")
        self.assertEqual(out["via"], "canned")
        self.assertFalse(out["live"])
        # canned never invokes the engine-live path.

    def test_run_live_not_called_in_canned_mode(self):
        with mock.patch.object(serve.live_engine, "run_live") as m:
            serve.route_api_run("anything at all", "canned")
        m.assert_not_called()

    def test_unknown_mode_defaults_to_engine_live(self):
        """An unrecognised ?mode= falls through to the live firm (forward-compatible default)."""
        with mock.patch.object(serve.live_engine, "run_live",
                               return_value=_fake_run_live_result()) as m:
            out = serve.route_api_run("Is TSC2 a viable CNS target?", "typo-mode")
        m.assert_called_once()
        self.assertEqual(out["via"], "engine-live")

    def test_engine_live_never_crashes_on_backend_error(self):
        """If run_live somehow raises, the endpoint returns an honest plan-only envelope."""
        with mock.patch.object(serve.live_engine, "run_live",
                               side_effect=RuntimeError("backend down")):
            out = serve.route_api_run("Is TSC2 a viable CNS target?", "live")
        self.assertFalse(out["live"])
        self.assertEqual(out["via"], "plan")
        self.assertIn("note", out)


class TestRealRunLiveConformsToContract(unittest.TestCase):
    """A REAL run_live (mock backends, real moat if present) conforms to the schema."""

    def setUp(self):
        self._eng = tempfile.mkdtemp()
        self._mem = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._mem

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def test_real_run_live_conforms(self):
        from tests.test_live_engine import _build_ctx
        result = serve.live_engine.run_live(
            "Is TSC2 a viable target in tuberous sclerosis?", ctx=_build_ctx())
        errs = validate_run_live(result)
        self.assertEqual(errs, [], f"run_live output drifted from its contract: {errs}")


if __name__ == "__main__":
    unittest.main()
