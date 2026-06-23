"""
tests/test_geneset_enrichment_seam.py — unit tests for the g:Profiler enrichment seam.

Offline/$0: the network is monkeypatched at the seam's single _fetch(genes) boundary
with a RECORDED g:GOSt response (captured live from g:Profiler on 2026-06-23 for
{TSC1, TSC2, MTOR}). One guarded live test hits the real public API; it skips unless
SAPPHIRE_LIVE_TESTS=1 and skips cleanly if the host is unreachable (e.g. a CA store
without the HARICA root — see the seam/report notes).

Run from sapphire-orchestrator/:
    python -m unittest tests.test_geneset_enrichment_seam -v
"""
from __future__ import annotations

import os
import sys
import unittest
import urllib.error
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_ORCH_ROOT = os.path.dirname(_HERE)
if _ORCH_ROOT not in sys.path:
    sys.path.insert(0, _ORCH_ROOT)

from tools import geneset_enrichment_seam as seam  # noqa: E402


# ── Recorded fixture (real g:GOSt terms for {TSC1,TSC2,MTOR}; trimmed) ────────
_FIXTURE = {"result": [
    {"native": "HP:0032051", "name": "Focal cortical dysplasia type II", "source": "HP",
     "p_value": 3.0497e-07, "significant": True, "intersection_size": 3},
    {"native": "WP:WP4141", "name": "PI3K AKT mTOR vitamin D3 signaling", "source": "WP",
     "p_value": 9.52e-07, "significant": True, "intersection_size": 3},
    {"native": "REAC:R-HSA-380972", "name": "Energy dependent regulation of mTOR by LKB1-AMPK",
     "source": "REAC", "p_value": 2.98e-06, "significant": True, "intersection_size": 3},
    {"native": "GO:0099999", "name": "a not-significant term", "source": "GO:BP",
     "p_value": 0.42, "significant": False, "intersection_size": 1},
]}

_FIXTURE_NONE_SIG = {"result": [
    {"native": "GO:0099999", "name": "nope", "source": "GO:BP", "p_value": 0.8, "significant": False},
]}


def _fake_fetch(resp, calls=None):
    def _f(genes):
        if calls is not None:
            calls.append(list(genes))
        return resp
    return _f


class TestGenesetSeamParsing(unittest.TestCase):

    def test_parses_set_into_one_t2_fact(self):
        with mock.patch.object(seam, "_fetch", _fake_fetch(_FIXTURE)):
            out = seam.findings({"genes": ["TSC1", "TSC2", "MTOR"], "candidate": "TSC1"})
        self.assertEqual(out["provenance"], "gprofiler")
        self.assertNotIn("error", out)
        self.assertEqual(len(out["facts"]), 1, out["facts"])
        val = out["facts"][0]["value"]
        self.assertIn("3 significant terms", val, val)                 # the non-significant row is excluded
        self.assertIn("Focal cortical dysplasia type II", val, val)
        self.assertIn("HP:0032051", val, val)
        self.assertIn("p=3.0e-07", val, val)
        self.assertIn("TSC1, TSC2, MTOR", val, val)
        self.assertNotIn("a not-significant term", val, val)
        self.assertEqual(out["facts"][0]["tier"], "T2")
        self.assertIn("g:Profiler", out["facts"][0]["source"])

    def test_fact_has_only_schema_allowed_keys(self):
        with mock.patch.object(seam, "_fetch", _fake_fetch(_FIXTURE)):
            out = seam.findings({"genes": ["TSC1", "TSC2"]})
        self.assertEqual(set(out["facts"][0].keys()), {"value", "source", "tier"})

    def test_genes_list_is_what_is_queried(self):
        calls = []
        with mock.patch.object(seam, "_fetch", _fake_fetch(_FIXTURE, calls)):
            seam.findings({"genes": ["TSC1", "TSC2"], "candidate": "TSC1"})
        self.assertEqual(calls[0], ["TSC1", "TSC2"])

    def test_single_candidate_fallback_when_no_gene_list(self):
        calls = []
        with mock.patch.object(seam, "_fetch", _fake_fetch(_FIXTURE, calls)):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(calls[0], ["TSC2"])                            # degenerate single-gene set
        self.assertEqual(len(out["facts"]), 1)

    def test_dedupes_and_strips_genes(self):
        calls = []
        with mock.patch.object(seam, "_fetch", _fake_fetch(_FIXTURE, calls)):
            seam.findings({"genes": [" TSC1 ", "TSC2", "TSC1", ""]})
        self.assertEqual(calls[0], ["TSC1", "TSC2"])


class TestGenesetSeamHonestDegradation(unittest.TestCase):

    def test_no_genes_honest_empty(self):
        out = seam.findings({})
        self.assertEqual(out["facts"], [])
        self.assertEqual(out["provenance"], "gprofiler")
        self.assertNotIn("error", out)

    def test_no_significant_terms_honest_empty(self):
        with mock.patch.object(seam, "_fetch", _fake_fetch(_FIXTURE_NONE_SIG)):
            out = seam.findings({"genes": ["TSC2"]})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)

    def test_empty_result_honest_empty(self):
        with mock.patch.object(seam, "_fetch", _fake_fetch({"result": []})):
            out = seam.findings({"genes": ["TSC2"]})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)

    def test_transport_or_tls_error_returns_envelope_never_raises(self):
        def _boom(genes):
            raise urllib.error.URLError("[SSL: CERTIFICATE_VERIFY_FAILED] ...")

        with mock.patch.object(seam, "_fetch", _boom):
            try:
                out = seam.findings({"genes": ["TSC1", "TSC2"]})
            except Exception as exc:  # noqa: BLE001
                self.fail(f"findings() raised instead of degrading honestly: {exc!r}")
        self.assertEqual(out["facts"], [])
        self.assertIn("error", out)
        self.assertEqual(out["provenance"], "gprofiler")


@unittest.skipUnless(
    os.environ.get("SAPPHIRE_LIVE_TESTS") == "1",
    "live g:Profiler API test (set SAPPHIRE_LIVE_TESTS=1; hits the public API, $0)",
)
class TestGenesetSeamLive(unittest.TestCase):

    def test_live_mtor_set(self):
        out = seam.findings({"genes": ["TSC1", "TSC2", "MTOR"]})
        if out.get("error"):
            # e.g. a CA store without the HARICA root (this Windows box); the chain is
            # valid and this verifies on standard CA stores (Mac/Linux).
            self.skipTest(f"g:Profiler unreachable from this env: {out['error']}")
        self.assertEqual(len(out["facts"]), 1)
        val = out["facts"][0]["value"]
        self.assertIn("significant terms", val)
        self.assertEqual(out["facts"][0]["tier"], "T2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
