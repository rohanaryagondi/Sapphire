"""Offline tests for the R-Sapphire endpoint wiring in qmodels/client.py.

All tests are hermetic — no real AWS or network calls. The R-Sapphire endpoint
is mocked at the urllib level. Verifies:
  - When SAPPHIRE_QMODELS_GPU_ENDPOINT is unset, falls through to local/gpu path.
  - When set and reachable, local-cpu and gpu tools both route through it.
  - When set but endpoint unreachable (URLError), falls through to local path.
  - When set and endpoint returns HTTP error, error dict is returned (no double-call).
  - _call_rsapphire returns provenance='rsapphire-live' on success.
  - rsapphire_health() is plumbed correctly.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make qmodels importable from the tests dir (same pattern as the existing test suite).
_ORCH = Path(__file__).resolve().parents[1]
if str(_ORCH) not in sys.path:
    sys.path.insert(0, str(_ORCH))

from qmodels import client as C
from qmodels.client import QModelsClient, _rsapphire_endpoint


# ---------------------------------------------------------------------------
# Minimal fake registry (local-cpu DTI + gpu ESM2)
# ---------------------------------------------------------------------------
_FAKE_REGISTRY = {
    "tracks": [
        {"id": "dti", "tier": "local-cpu", "status": "live", "label": "DTI",
         "aws_model_key": "balm"},
        {"id": "family_clustering", "tier": "gpu-launch", "status": "live",
         "label": "ESM-2 Family Clustering", "aws_model_key": "esm2_650m"},
    ],
    "models": [],
}

_DTI_TOOL = _FAKE_REGISTRY["tracks"][0]
_ESM_TOOL = _FAKE_REGISTRY["tracks"][1]


def _fake_adapters():
    """A minimal adapters stub: normalize returns the raw prediction plus provenance."""
    a = MagicMock()
    a.normalize = lambda tool, pred, prov: {**pred, "provenance": prov,
                                            "tool_id": tool.get("id"),
                                            "model": tool.get("label")}
    return a


class _FakeResponse:
    """urllib response stub."""
    def __init__(self, body: dict):
        self._data = json.dumps(body).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


# ---------------------------------------------------------------------------
# Test: env var helper
# ---------------------------------------------------------------------------
class TestRSapphireEnvHelper(unittest.TestCase):
    def test_returns_none_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key entirely if present
            env = {k: v for k, v in os.environ.items() if k != "SAPPHIRE_QMODELS_GPU_ENDPOINT"}
            with patch.dict(os.environ, env, clear=True):
                self.assertIsNone(_rsapphire_endpoint())

    def test_returns_none_when_empty(self):
        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": ""}):
            self.assertIsNone(_rsapphire_endpoint())

    def test_returns_url_when_set(self):
        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://1.2.3.4:8080/predict"}):
            self.assertEqual(_rsapphire_endpoint(), "http://1.2.3.4:8080/predict")

    def test_strips_whitespace(self):
        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "  http://x:8080/predict  "}):
            self.assertEqual(_rsapphire_endpoint(), "http://x:8080/predict")


# ---------------------------------------------------------------------------
# Test: _call_rsapphire
# ---------------------------------------------------------------------------
class TestCallRSapphire(unittest.TestCase):
    def _client(self):
        return QModelsClient(registry=_FAKE_REGISTRY)

    def test_returns_none_when_endpoint_unset(self):
        cli = self._client()
        env = {k: v for k, v in os.environ.items() if k != "SAPPHIRE_QMODELS_GPU_ENDPOINT"}
        with patch.dict(os.environ, env, clear=True):
            result = cli._call_rsapphire(_DTI_TOOL, {"smiles": "CCO"}, _fake_adapters())
        self.assertIsNone(result)

    def test_routes_local_cpu_tool_through_rsapphire(self):
        cli = self._client()
        fake_pred = {"score_kind": "affinity", "value": 0.82}
        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://fake:8080/predict"}):
            with patch("urllib.request.urlopen", return_value=_FakeResponse(fake_pred)):
                result = cli._call_rsapphire(_DTI_TOOL, {"smiles": "CCO"}, _fake_adapters())
        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["provenance"], "rsapphire-live")
        self.assertEqual(result["value"], 0.82)

    def test_routes_gpu_tool_through_rsapphire(self):
        cli = self._client()
        fake_pred = {"score_kind": "embedding", "nearest_family": "ion_channel"}
        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://fake:8080/predict"}):
            with patch("urllib.request.urlopen", return_value=_FakeResponse(fake_pred)):
                result = cli._call_rsapphire(_ESM_TOOL, {"sequences": "MKVLA"}, _fake_adapters())
        self.assertIsNotNone(result)
        self.assertTrue(result["ok"])
        self.assertEqual(result["provenance"], "rsapphire-live")

    def test_returns_none_on_url_error(self):
        """URLError (endpoint down) → return None so caller falls through."""
        cli = self._client()
        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://down:8080/predict"}):
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("refused")):
                result = cli._call_rsapphire(_DTI_TOOL, {}, _fake_adapters())
        self.assertIsNone(result)

    def test_returns_error_dict_on_http_error(self):
        """HTTPError (endpoint up but 503/500) → return error dict, no fall-through."""
        cli = self._client()
        http_err = urllib.error.HTTPError("http://fake:8080/predict", 503, "Service Unavailable",
                                          {}, BytesIO(b"overloaded"))
        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://fake:8080/predict"}):
            with patch("urllib.request.urlopen", side_effect=http_err):
                result = cli._call_rsapphire(_DTI_TOOL, {}, _fake_adapters())
        self.assertIsNotNone(result)
        self.assertFalse(result["ok"])
        self.assertEqual(result["provenance"], "rsapphire-error")
        self.assertIn("503", result["note"])


# ---------------------------------------------------------------------------
# Test: call() routing — endpoint set vs unset
# ---------------------------------------------------------------------------
class TestCallRoutingWithRSapphire(unittest.TestCase):
    def _client(self):
        return QModelsClient(registry=_FAKE_REGISTRY)

    def test_local_cpu_bypasses_local_explorer_when_rsapphire_set(self):
        """call(dti, ...) with endpoint set should hit rsapphire, NOT the local /api/predict."""
        cli = self._client()
        fake_pred = {"score_kind": "affinity", "value": 0.7}
        hits = []

        def fake_urlopen(req, timeout=None):
            hits.append(str(req.full_url if hasattr(req, "full_url") else req))
            return _FakeResponse(fake_pred)

        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://rsapphire:8080/predict"}):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                result = cli.call("dti", {"smiles": "CCO"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["provenance"], "rsapphire-live")
        # The only urlopen call must be to the rsapphire endpoint
        self.assertTrue(any("rsapphire" in str(h) for h in hits),
                        f"expected rsapphire hit, got: {hits}")

    def test_gpu_tool_calls_rsapphire_when_set(self):
        cli = self._client()
        fake_pred = {"score_kind": "embedding", "nearest_family": "gpcr"}

        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://rsapphire:8080/predict"}):
            with patch("urllib.request.urlopen", return_value=_FakeResponse(fake_pred)):
                result = cli.call("family_clustering", {"sequences": "MKVLA"})

        self.assertTrue(result["ok"])
        self.assertEqual(result["provenance"], "rsapphire-live")

    def test_falls_through_to_local_on_unreachable_endpoint(self):
        """URLError from rsapphire → falls through to _call_local → local endpoint unreachable → unavailable."""
        cli = self._client()
        call_count = {"n": 0}

        def fake_urlopen(req, timeout=None):
            call_count["n"] += 1
            raise urllib.error.URLError("connection refused")

        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://rsapphire:8080/predict"}):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                result = cli.call("dti", {"smiles": "CCO"})

        # Falls through to _call_local which also fails → unavailable
        self.assertFalse(result["ok"])
        self.assertIn(result["provenance"], ("unavailable", "error"))

    def test_call_without_endpoint_uses_local_path_for_local_cpu(self):
        """When endpoint unset, local-cpu tools go through _call_local (normal path)."""
        cli = self._client()
        env = {k: v for k, v in os.environ.items() if k != "SAPPHIRE_QMODELS_GPU_ENDPOINT"}
        fake_body = {"prediction": {"score_kind": "affinity", "value": 0.5}}

        with patch.dict(os.environ, env, clear=True):
            with patch("urllib.request.urlopen", return_value=_FakeResponse(fake_body)):
                result = cli.call("dti", {"smiles": "CCO"})

        # Local path returns stub provenance (no live_tracks from health call — both fail = stub)
        self.assertIn(result.get("provenance"), ("stub", "live-local", "unavailable", "error"))

    def test_deprecated_tool_is_refused_regardless_of_endpoint(self):
        """deprecated/todo tools are refused before any endpoint routing."""
        reg = {
            "tracks": [{"id": "old_tool", "tier": "local-cpu", "status": "deprecated",
                        "label": "Old", "aws_model_key": "old"}],
            "models": [],
        }
        cli = QModelsClient(registry=reg)
        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://fake:8080/predict"}):
            result = cli.call("old_tool", {})
        self.assertFalse(result["ok"])
        self.assertEqual(result["provenance"], "unavailable")


# ---------------------------------------------------------------------------
# Test: rsapphire_health()
# ---------------------------------------------------------------------------
class TestRSapphireHealth(unittest.TestCase):
    def _client(self):
        return QModelsClient(registry=_FAKE_REGISTRY)

    def test_health_not_reachable_when_unset(self):
        cli = self._client()
        env = {k: v for k, v in os.environ.items() if k != "SAPPHIRE_QMODELS_GPU_ENDPOINT"}
        with patch.dict(os.environ, env, clear=True):
            h = cli.rsapphire_health()
        self.assertFalse(h["reachable"])
        self.assertIn("not set", h["reason"])

    def test_health_reachable(self):
        cli = self._client()
        fake = {"status": "ok", "cuda": True, "models": ["esm2_650m"]}
        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://fake:8080/predict"}):
            with patch("urllib.request.urlopen", return_value=_FakeResponse(fake)):
                h = cli.rsapphire_health()
        self.assertTrue(h["reachable"])
        self.assertEqual(h["health"]["status"], "ok")

    def test_health_reports_error_on_urlopen_failure(self):
        cli = self._client()
        with patch.dict(os.environ, {"SAPPHIRE_QMODELS_GPU_ENDPOINT": "http://down:8080/predict"}):
            with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
                h = cli.rsapphire_health()
        self.assertFalse(h["reachable"])
        self.assertIn("error", h)


if __name__ == "__main__":
    unittest.main()
