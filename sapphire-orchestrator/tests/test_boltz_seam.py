"""
tests/test_boltz_seam.py — unit tests for the Boltz structure/binding seam.

All tests are offline/$0 and use NO live key: the network is monkeypatched at the
seam's single ``_http`` boundary with RECORDED Boltz Compute API response shapes
(captured live 2026-06-25 for a tiny public fold + synthesised binding cases), and
``_sleep`` is monkeypatched out so the poll loop doesn't actually wait. The real key
is NEVER read in these tests — ``_resolve_key`` is patched to a dummy string.

A clearly-guarded live integration test (opt-in via SAPPHIRE_LIVE_TESTS=1) does a
single cheap $0 cost-estimate against the real API and skips when offline/keyless.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_boltz_seam -v
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

# Ensure sapphire-orchestrator is on sys.path when running from repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ORCH_ROOT = os.path.dirname(_HERE)
if _ORCH_ROOT not in sys.path:
    sys.path.insert(0, _ORCH_ROOT)

from tools import boltz_seam as seam  # noqa: E402
from contracts import provenance as prov  # noqa: E402


# ── Recorded fixtures (verbatim shapes returned by the live API on 2026-06-25) ──

# A successful START response (status pending, output null). Key fields only.
_START_PENDING = {
    "id": "sab_pred_TESTONLY0001",
    "status": "pending",
    "output": None,
    "error": None,
    "model": "boltz-2.1",
}

# A terminal RETRIEVE response for a fold-only job (no binding requested).
# Numbers are the real captured values for the MKTAYIAKQR fold.
_RETRIEVE_SUCCEEDED_FOLD = {
    "id": "sab_pred_TESTONLY0001",
    "status": "succeeded",
    "error": None,
    "output": {
        "best_sample": {
            "metrics": {
                "structure_confidence": 0.7988103628158569,
                "ptm": 0.22313454747200012,
                "iptm": 0.0,
                "ligand_iptm": 0.0,
                "protein_iptm": 0.0,
                "complex_plddt": 0.9427292943000793,
                "complex_iplddt": 0.0,
                "complex_pde": 0.0,
                "complex_ipde": 0.0,
            }
        },
        "all_sample_results": [],
        "archive": {},
    },
}

# A terminal RETRIEVE for a ligand-protein binding job (binding_metrics present).
_RETRIEVE_SUCCEEDED_BINDING = {
    "id": "sab_pred_TESTONLY0002",
    "status": "succeeded",
    "error": None,
    "output": {
        "best_sample": {"metrics": {"structure_confidence": 0.91, "complex_plddt": 0.88,
                                    "ptm": 0.7, "iptm": 0.65}},
        "binding_metrics": {
            "binding_confidence": 0.83,
            "optimization_score": 0.42,
            "type": "ligand_protein_binding_metrics",
        },
    },
}

# A terminal FAILED job.
_RETRIEVE_FAILED = {
    "id": "sab_pred_TESTONLY0003",
    "status": "failed",
    "error": {"code": "MODEL_ERROR", "message": "sampling diverged"},
    "output": None,
}

# A succeeded job with an empty/missing output (degenerate).
_RETRIEVE_SUCCEEDED_NO_OUTPUT = {
    "id": "sab_pred_TESTONLY0004", "status": "succeeded", "error": None, "output": None,
}


def _fake_http_factory(retrieve_record, *, running_polls=0):
    """Return a fake ``_http(method, path, api_key, body=None)`` that returns the
    START_PENDING on POST, then ``running`` for ``running_polls`` GETs, then the given
    terminal ``retrieve_record``."""
    state = {"polls": 0}

    def _fake(method, path, api_key, body=None):
        if method == "POST":
            return dict(_START_PENDING)
        # GET poll
        state["polls"] += 1
        if state["polls"] <= running_polls:
            return {"id": _START_PENDING["id"], "status": "running", "output": None, "error": None}
        return retrieve_record
    return _fake


class TestBoltzNormalize(unittest.TestCase):
    """normalize() turns a terminal job into cited T2 facts — no fabrication."""

    def test_fold_only_emits_structure_fact(self):
        facts = seam.normalize(_RETRIEVE_SUCCEEDED_FOLD, requested_binding=False)
        self.assertEqual(len(facts), 1, facts)
        f = facts[0]
        self.assertEqual(f["tier"], "T2")
        self.assertIn("structure_confidence 0.80", f["value"], f["value"])  # 0.7988 → 0.80
        self.assertIn("complex_pLDDT 0.94", f["value"], f["value"])
        # 0.7988 is BELOW the 0.80 high-confidence threshold (the real value, not the
        # rounded display), so the seam must NOT over-claim it as high-confidence.
        self.assertNotIn("high-confidence", f["value"], f["value"])
        self.assertNotIn("low-confidence", f["value"], f["value"])   # nor low (>= 0.50)
        self.assertIn("Boltz", f["source"])
        self.assertNotIn("binding", f["value"].lower())  # no binding requested

    def test_high_confidence_label_at_threshold(self):
        rec = {"status": "succeeded", "error": None,
               "output": {"best_sample": {"metrics": {"structure_confidence": 0.85}}}}
        facts = seam.normalize(rec, requested_binding=False)
        self.assertIn("high-confidence fold", facts[0]["value"], facts[0]["value"])

    def test_binding_emits_two_facts(self):
        facts = seam.normalize(_RETRIEVE_SUCCEEDED_BINDING, requested_binding=True)
        vals = " || ".join(f["value"] for f in facts)
        self.assertEqual(len(facts), 2, facts)
        self.assertIn("structure_confidence 0.91", vals, vals)
        self.assertIn("binding_confidence 0.83", vals, vals)
        self.assertIn("optimization_score 0.42", vals, vals)
        self.assertTrue(all(f["tier"] == "T2" for f in facts))

    def test_binding_metrics_ignored_when_not_requested(self):
        # Even if binding_metrics is present, don't surface it unless it was requested.
        facts = seam.normalize(_RETRIEVE_SUCCEEDED_BINDING, requested_binding=False)
        vals = " ".join(f["value"] for f in facts)
        self.assertNotIn("binding_confidence", vals, vals)

    def test_failed_job_is_known_unknown_not_fabrication(self):
        facts = seam.normalize(_RETRIEVE_FAILED, requested_binding=False)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["flag"], "KNOWN_UNKNOWN")
        self.assertIn("failed", facts[0]["value"].lower())
        self.assertIn("sampling diverged", facts[0]["value"])

    def test_succeeded_no_output_is_known_unknown(self):
        facts = seam.normalize(_RETRIEVE_SUCCEEDED_NO_OUTPUT, requested_binding=False)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["flag"], "KNOWN_UNKNOWN")

    def test_no_low_confidence_overclaim(self):
        rec = {"status": "succeeded", "error": None,
               "output": {"best_sample": {"metrics": {"structure_confidence": 0.30}}}}
        facts = seam.normalize(rec, requested_binding=False)
        self.assertIn("low-confidence fold", facts[0]["value"], facts[0]["value"])
        self.assertNotIn("high-confidence", facts[0]["value"])


class TestBoltzPredictLifecycle(unittest.TestCase):
    """predict() drives start → poll → terminal through the mocked _http boundary."""

    def test_fold_prediction_success_shape(self):
        fake = _fake_http_factory(_RETRIEVE_SUCCEEDED_FOLD, running_polls=2)
        with mock.patch.object(seam, "_resolve_key", lambda: "DUMMY_TEST_KEY"), \
             mock.patch.object(seam, "_http", fake), \
             mock.patch.object(seam, "_sleep", lambda s: None):
            out = seam.predict([{"type": "protein", "chain_ids": ["A"], "value": "MKTAYIAKQR"}])
        self.assertEqual(out["provenance"], "boltz")
        self.assertEqual(out["status"], "succeeded")
        self.assertEqual(len(out["facts"]), 1)
        self.assertNotIn("error", out)

    def test_polls_until_terminal(self):
        # 3 running polls then succeeded — must keep polling and not give up early.
        fake = _fake_http_factory(_RETRIEVE_SUCCEEDED_FOLD, running_polls=3)
        with mock.patch.object(seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(seam, "_http", fake), \
             mock.patch.object(seam, "_sleep", lambda s: None):
            out = seam.predict([{"type": "protein", "chain_ids": ["A"], "value": "AAAA"}])
        self.assertEqual(out["status"], "succeeded")

    def test_empty_entities_no_input(self):
        out = seam.predict([])
        self.assertEqual(out["facts"], [])
        self.assertEqual(out["status"], "no_input")
        self.assertEqual(out["provenance"], "boltz")


class TestBoltzHonestDegradation(unittest.TestCase):

    def test_missing_key_is_known_unknown_never_fabricates(self):
        with mock.patch.object(seam, "_resolve_key", lambda: None):
            out = seam.predict([{"type": "protein", "chain_ids": ["A"], "value": "AAAA"}])
        self.assertEqual(out["status"], "no_key")
        self.assertEqual(len(out["facts"]), 1)
        self.assertEqual(out["facts"][0]["flag"], "KNOWN_UNKNOWN")
        self.assertIn("error", out)
        self.assertEqual(out["provenance"], "boltz")

    def test_transport_error_returns_envelope_never_raises(self):
        def _boom(method, path, api_key, body=None):
            raise urllib.error.URLError("connection refused")
        with mock.patch.object(seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(seam, "_http", _boom), \
             mock.patch.object(seam, "_sleep", lambda s: None):
            try:
                out = seam.predict([{"type": "protein", "chain_ids": ["A"], "value": "AAAA"}])
            except Exception as exc:  # noqa: BLE001
                self.fail(f"predict() raised instead of degrading honestly: {exc!r}")
        self.assertEqual(out["status"], "unreachable")
        self.assertEqual(out["facts"][0]["flag"], "KNOWN_UNKNOWN")
        self.assertIn("error", out)

    def test_timeout_is_known_unknown(self):
        # _http always returns 'running' → never terminal → TimeoutError → honest degrade.
        def _always_running(method, path, api_key, body=None):
            if method == "POST":
                return dict(_START_PENDING)
            return {"id": _START_PENDING["id"], "status": "running", "output": None}
        with mock.patch.object(seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(seam, "_http", _always_running), \
             mock.patch.object(seam, "_sleep", lambda s: None), \
             mock.patch.object(seam, "_MAX_POLLS", 3):
            out = seam.predict([{"type": "protein", "chain_ids": ["A"], "value": "AAAA"}])
        self.assertEqual(out["status"], "timeout")
        self.assertEqual(out["facts"][0]["flag"], "KNOWN_UNKNOWN")

    def test_start_without_id_is_error(self):
        def _no_id(method, path, api_key, body=None):
            return {"status": "pending", "error": {"message": "bad request"}}  # no id
        with mock.patch.object(seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(seam, "_http", _no_id), \
             mock.patch.object(seam, "_sleep", lambda s: None):
            out = seam.predict([{"type": "protein", "chain_ids": ["A"], "value": "AAAA"}])
        self.assertEqual(out["status"], "error")
        self.assertEqual(out["facts"][0]["flag"], "KNOWN_UNKNOWN")


class TestBoltzPublicOnlyBoundary(unittest.TestCase):
    """Boltz must receive PUBLIC identifiers only — internal-data tripwire."""

    def test_internal_marker_blocks_transmission(self):
        # assert_public_only raises on internal markers.
        for bad in ["EP-12345", "moat_CRISPR_SCORE_0.9", "CNS_DFP row 7", "QUIVER_INTERNAL"]:
            with self.assertRaises(ValueError, msg=bad):
                seam.assert_public_only([{"type": "protein", "chain_ids": ["A"], "value": bad}])

    def test_public_inputs_pass(self):
        # A normal protein sequence + SMILES must NOT trip the wire.
        try:
            seam.assert_public_only([
                {"type": "protein", "chain_ids": ["A"], "value": "MKTAYIAKQRQISFVKSHFSRQ"},
                {"type": "ligand_smiles", "chain_ids": ["B"], "value": "CC(=O)Oc1ccccc1C(=O)O"},
            ])
        except ValueError as exc:  # noqa: BLE001
            self.fail(f"public inputs wrongly blocked: {exc}")

    def test_predict_blocks_internal_without_calling_api(self):
        called = {"http": False}

        def _spy(*a, **k):
            called["http"] = True
            return {}
        with mock.patch.object(seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(seam, "_http", _spy):
            out = seam.predict([{"type": "protein", "chain_ids": ["A"], "value": "EP-9001"}])
        self.assertFalse(called["http"], "internal data must NOT reach the network")
        self.assertEqual(out["status"], "boundary_block")
        self.assertEqual(out["facts"][0]["flag"], "KNOWN_UNKNOWN")


class TestBoltzFindings(unittest.TestCase):
    """findings(inputs) — the harness entrypoint + its output contract."""

    def test_no_structural_input_is_honest_empty(self):
        out = seam.findings({"candidate": "TSC2"})  # gene symbol only, no sequence
        self.assertEqual(out["facts"], [])
        self.assertEqual(out["provenance"], "boltz")
        self.assertNotIn("error", out)

    def test_protein_plus_ligand_auto_binding(self):
        captured = {}

        def _fake(method, path, api_key, body=None):
            if method == "POST":
                captured["body"] = body
                return dict(_START_PENDING)
            return _RETRIEVE_SUCCEEDED_BINDING
        with mock.patch.object(seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(seam, "_http", _fake), \
             mock.patch.object(seam, "_sleep", lambda s: None):
            out = seam.findings({
                "candidate": "TARGETX",
                "target_sequence": "MKTAYIAKQRQISFVKSHFSRQ",
                "ligand_smiles": "CC(=O)Oc1ccccc1C(=O)O",
            })
        # Auto binding block was added (protein A + ligand B).
        self.assertEqual(captured["body"]["input"]["binding"],
                         {"type": "ligand_protein_binding", "binder_chain_id": "B"})
        self.assertEqual(out["candidate"], "TARGETX")
        self.assertEqual(out["provenance"], "boltz")
        vals = " ".join(f["value"] for f in out["facts"])
        self.assertIn("binding_confidence", vals, vals)

    def test_findings_fact_keys_are_schema_allowed(self):
        """Facts must carry only value/source/tier[/flag] — keys the harness
        output_schema (additionalProperties:false) permits."""
        allowed = {"value", "source", "tier", "flag", "provenance"}
        with mock.patch.object(seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(seam, "_http",
                               _fake_http_factory(_RETRIEVE_SUCCEEDED_FOLD)), \
             mock.patch.object(seam, "_sleep", lambda s: None):
            out = seam.findings({"candidate": "X", "target_sequence": "MKTAYIAKQR"})
        for f in out["facts"]:
            self.assertTrue(set(f.keys()) <= allowed, f"unexpected keys: {f.keys()}")

    def test_findings_never_raises_on_transport_error(self):
        def _boom(method, path, api_key, body=None):
            raise urllib.error.URLError("down")
        with mock.patch.object(seam, "_resolve_key", lambda: "DUMMY"), \
             mock.patch.object(seam, "_http", _boom), \
             mock.patch.object(seam, "_sleep", lambda s: None):
            out = seam.findings({"candidate": "X", "target_sequence": "AAAA"})
        self.assertEqual(out["provenance"], "boltz")
        self.assertIn("error", out)
        self.assertEqual(out["facts"][0]["flag"], "KNOWN_UNKNOWN")


class TestBoltzProvenanceContract(unittest.TestCase):
    """The 'boltz' provenance label is registered and EXTERNAL-plane."""

    def test_boltz_is_valid_provenance(self):
        self.assertTrue(prov.is_valid_provenance("boltz"))
        self.assertIn("boltz", prov.PROVENANCE)

    def test_boltz_is_external_plane_not_internal(self):
        self.assertEqual(prov.plane_for("boltz"), "external")

    def test_internal_fact_never_routes_to_boltz(self):
        # An internal-plane fact bound for a boltz-provenance agent is a boundary violation.
        self.assertTrue(prov.is_boundary_violation("boltz", "internal"))
        # An external-plane fact is fine.
        self.assertFalse(prov.is_boundary_violation("boltz", "external"))


class _FakeUrlResponse:
    """Minimal urllib response stub for R-Sapphire routing tests."""
    def __init__(self, body: dict):
        import io
        self._data = json.dumps(body).encode()
        self._bio = io.BytesIO(self._data)

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class TestBoltzRSapphireRouting(unittest.TestCase):
    """When SAPPHIRE_QMODELS_GPU_ENDPOINT is set, predict() routes boltz through
    R-Sapphire's boltz2 model — NOT the hosted Boltz API (which needs BOLTZ_API_KEY)."""

    def _entities(self):
        return [
            {"type": "protein", "chain_ids": ["A"], "value": "MKTAYIAKQR"},
            {"type": "ligand_smiles", "chain_ids": ["B"], "value": "CCO"},
        ]

    def test_routes_through_rsapphire_when_endpoint_set(self):
        """With endpoint set: _predict_via_rsapphire is called; hosted _http is NOT called."""
        hits = {"rsapphire": 0, "hosted": 0}

        def _fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "boltz.bio" in url:
                hits["hosted"] += 1
            elif "54.164" in url or "rsapphire" in url or "8080" in url:
                hits["rsapphire"] += 1
            return _FakeUrlResponse({"structure_confidence": 0.82, "binding_confidence": 0.75})

        with mock.patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://rsapphire:8080/predict"}), \
             mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            out = seam.predict(self._entities())

        self.assertEqual(hits["hosted"], 0, "hosted Boltz API must NOT be called when endpoint set")
        self.assertGreater(hits["rsapphire"], 0, "R-Sapphire endpoint must be called")
        self.assertEqual(out["provenance"], "boltz-rsapphire")
        self.assertGreater(len(out["facts"]), 0, "must return at least one fact")

    def test_rsapphire_result_carries_structure_and_binding_facts(self):
        """When R-Sapphire returns structure_confidence + binding_confidence, both appear."""
        def _fake_urlopen(req, timeout=None):
            return _FakeUrlResponse({"structure_confidence": 0.85, "binding_confidence": 0.72})

        with mock.patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://rsapphire:8080/predict"}), \
             mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen):
            out = seam.predict(self._entities())

        vals = " || ".join(f["value"] for f in out["facts"])
        self.assertIn("structure_confidence 0.85", vals, vals)
        self.assertIn("binding_confidence 0.72", vals, vals)

    def test_falls_through_to_hosted_api_when_endpoint_unreachable(self):
        """URLError from R-Sapphire endpoint → falls through to hosted path → no_key degradation."""
        import urllib.error as ue

        call_count = {"rsapphire": 0}

        def _fake_urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "rsapphire" in url or "8080" in url:
                call_count["rsapphire"] += 1
                raise ue.URLError("connection refused")
            raise ue.URLError("hosted also down")

        with mock.patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://rsapphire:8080/predict"}), \
             mock.patch("urllib.request.urlopen", side_effect=_fake_urlopen), \
             mock.patch.object(seam, "_resolve_key", lambda: None):
            out = seam.predict(self._entities())

        # R-Sapphire was tried (then fell through); no_key since BOLTZ_API_KEY also absent.
        self.assertGreater(call_count["rsapphire"], 0, "R-Sapphire must be attempted first")
        self.assertEqual(out["status"], "no_key", f"expected no_key degrade, got {out}")

    def test_no_rsapphire_call_when_endpoint_unset(self):
        """When endpoint env is unset, skip R-Sapphire entirely → no_key (honest)."""
        env = {k: v for k, v in os.environ.items() if k != "SAPPHIRE_QMODELS_GPU_ENDPOINT"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch.object(seam, "_resolve_key", lambda: None):
            out = seam.predict(self._entities())
        self.assertEqual(out["status"], "no_key")
        self.assertEqual(out["provenance"], "boltz")

    def test_rsapphire_http_error_is_honest_degrade_not_raises(self):
        """HTTP 500 from R-Sapphire endpoint → honest error fact, never raises."""
        import urllib.error as ue
        from io import BytesIO

        http_err = ue.HTTPError("http://rsapphire:8080/predict", 500, "Internal Server Error",
                                {}, BytesIO(b"Boltz-2 failed"))
        with mock.patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://rsapphire:8080/predict"}), \
             mock.patch("urllib.request.urlopen", side_effect=http_err):
            try:
                out = seam.predict(self._entities())
            except Exception as exc:
                self.fail(f"predict() raised instead of degrading: {exc!r}")
        self.assertEqual(out["provenance"], "boltz-rsapphire")
        self.assertIn("500", out.get("error", "") + " " + out["facts"][0]["value"])


@unittest.skipUnless(
    os.environ.get("SAPPHIRE_LIVE_TESTS") == "1",
    "live Boltz API test (set SAPPHIRE_LIVE_TESTS=1; does a $0 cost-estimate, needs the key)",
)
class TestBoltzLive(unittest.TestCase):
    """Hits the REAL Boltz API with a $0 cost-ESTIMATE (runs no model). Opt-in via
    SAPPHIRE_LIVE_TESTS=1; skips cleanly if no key / offline. Never submits a paid job."""

    def test_live_auth_and_estimate(self):
        api_key = seam._resolve_key()
        if not api_key:
            self.skipTest("no BOLTZ_API_KEY available")
        body = {
            "input": {"entities": [{"type": "protein", "chain_ids": ["A"],
                                    "value": "MKTAYIAKQR"}], "num_samples": 1},
            "model": "boltz-2.1",
        }
        try:
            out = seam._http("POST", seam._START_PATH + "/estimate-cost", api_key, body=body)
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"Boltz API unreachable: {exc}")
        self.assertIn("estimated_cost_usd", out)
        # Sanity: a 1-sample tiny fold estimate is a small positive dollar figure.
        self.assertGreaterEqual(float(out["estimated_cost_usd"]), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
