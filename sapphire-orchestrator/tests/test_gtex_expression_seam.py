"""
tests/test_gtex_expression_seam.py — unit tests for the GTEx expression seam.

Offline/$0: the network is monkeypatched at the seam's single _fetch(path, params)
boundary with RECORDED GTEx v2 responses (captured live from
https://gtexportal.org/api/v2 on 2026-06-23 for TSC2). One guarded live test hits
the real public API ($0) and skips unless SAPPHIRE_LIVE_TESTS=1.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_gtex_expression_seam -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
_ORCH_ROOT = os.path.dirname(_HERE)
if _ORCH_ROOT not in sys.path:
    sys.path.insert(0, _ORCH_ROOT)

from tools import gtex_expression_seam as seam  # noqa: E402


# ── Recorded fixtures ─────────────────────────────────────────────────────────

# /reference/gene?geneId=TSC2  (real shape; trimmed to fields the seam reads)
_GENE_TSC2 = {
    "data": [{
        "gencodeId": "ENSG00000103197.16", "geneSymbol": "TSC2",
        "geneSymbolUpper": "TSC2", "geneType": "protein coding",
    }],
    "paging_info": {"totalNumberOfItems": 1},
}

# /expression/medianGeneExpression — real TSC2 medians (subset; Cerebellum is the
# overall max, as in the full 54-tissue response).
_EXPR_TSC2 = {
    "data": [
        {"median": 133.226, "tissueSiteDetailId": "Brain_Cerebellum", "unit": "TPM"},
        {"median": 103.942, "tissueSiteDetailId": "Brain_Cerebellar_Hemisphere", "unit": "TPM"},
        {"median": 94.3068, "tissueSiteDetailId": "Pituitary", "unit": "TPM"},
        {"median": 87.945, "tissueSiteDetailId": "Thyroid", "unit": "TPM"},
        {"median": 86.254, "tissueSiteDetailId": "Testis", "unit": "TPM"},
        {"median": 40.1608, "tissueSiteDetailId": "Adipose_Subcutaneous", "unit": "TPM"},
        {"median": 38.1049, "tissueSiteDetailId": "Brain_Cortex", "unit": "TPM"},
    ],
    "paging_info": {"totalNumberOfItems": 7},
}

# A gene whose top brain region ranks > 5 (broadly expressed, NOT CNS-enriched).
_EXPR_BROAD = {"data": [
    {"median": 100.0, "tissueSiteDetailId": "Liver", "unit": "TPM"},
    {"median": 90.0, "tissueSiteDetailId": "Thyroid", "unit": "TPM"},
    {"median": 80.0, "tissueSiteDetailId": "Lung", "unit": "TPM"},
    {"median": 70.0, "tissueSiteDetailId": "Heart_Left_Ventricle", "unit": "TPM"},
    {"median": 60.0, "tissueSiteDetailId": "Kidney_Cortex", "unit": "TPM"},
    {"median": 50.0, "tissueSiteDetailId": "Muscle_Skeletal", "unit": "TPM"},
    {"median": 40.0, "tissueSiteDetailId": "Brain_Cortex", "unit": "TPM"},
    {"median": 35.0, "tissueSiteDetailId": "Brain_Cerebellum", "unit": "TPM"},
]}

# A gene with no brain tissue rows at all.
_EXPR_NO_BRAIN = {"data": [
    {"median": 50.0, "tissueSiteDetailId": "Liver", "unit": "TPM"},
    {"median": 40.0, "tissueSiteDetailId": "Thyroid", "unit": "TPM"},
]}


def _dispatcher(ref_resp, expr_resp, calls=None):
    """Build a fake _fetch(path, params) that routes by endpoint and optionally
    records calls."""
    def _f(path, params):
        if calls is not None:
            calls.append((path, dict(params)))
        if "reference/gene" in path:
            return ref_resp
        if "medianGeneExpression" in path:
            return expr_resp
        raise AssertionError(f"unexpected path {path}")
    return _f


class TestGtexSeamParsing(unittest.TestCase):

    def test_parses_tsc2_into_one_t1_cns_enriched_fact(self):
        with mock.patch.object(seam, "_fetch", _dispatcher(_GENE_TSC2, _EXPR_TSC2)):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(out["candidate"], "TSC2")
        self.assertEqual(out["provenance"], "gtex")
        self.assertNotIn("error", out)
        self.assertEqual(len(out["facts"]), 1, out["facts"])
        fact = out["facts"][0]
        # Non-vacuous: the real top brain region + number + selectivity must appear.
        self.assertIn("Brain Cerebellum 133.2", fact["value"], fact["value"])
        self.assertIn("CNS-enriched", fact["value"], fact["value"])
        self.assertIn("gtex_v8", fact["value"], fact["value"])
        self.assertEqual(fact["tier"], "T1")
        self.assertIn("GTEx", fact["source"])

    def test_fact_has_only_schema_allowed_keys(self):
        with mock.patch.object(seam, "_fetch", _dispatcher(_GENE_TSC2, _EXPR_TSC2)):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(set(out["facts"][0].keys()), {"value", "source", "tier"})

    def test_target_alias_accepted(self):
        with mock.patch.object(seam, "_fetch", _dispatcher(_GENE_TSC2, _EXPR_TSC2)):
            out = seam.findings({"target": "TSC2"})
        self.assertEqual(len(out["facts"]), 1)

    def test_expression_query_uses_resolved_gencode(self):
        """Proves the two-call flow: the gencodeId from /reference/gene is passed
        to /expression/medianGeneExpression with the pinned dataset."""
        calls = []
        with mock.patch.object(seam, "_fetch", _dispatcher(_GENE_TSC2, _EXPR_TSC2, calls)):
            seam.findings({"candidate": "TSC2"})
        expr = [p for (path, p) in calls if "medianGeneExpression" in path]
        self.assertEqual(len(expr), 1, calls)
        self.assertEqual(expr[0]["gencodeId"], "ENSG00000103197.16")
        self.assertEqual(expr[0]["datasetId"], "gtex_v8")

    def test_broadly_expressed_not_overclaimed(self):
        with mock.patch.object(seam, "_fetch", _dispatcher(_GENE_TSC2, _EXPR_BROAD)):
            out = seam.findings({"candidate": "SOMEGENE"})
        val = out["facts"][0]["value"]
        self.assertNotIn("CNS-enriched", val, val)
        self.assertIn("ranks #7 of 8", val, val)
        self.assertIn("broadly expressed", val, val)
        self.assertIn("Brain Cortex 40.0", val, val)

    def test_no_brain_tissue_reported_honestly(self):
        with mock.patch.object(seam, "_fetch", _dispatcher(_GENE_TSC2, _EXPR_NO_BRAIN)):
            out = seam.findings({"candidate": "SOMEGENE"})
        val = out["facts"][0]["value"]
        self.assertIn("no CNS tissue in dataset", val, val)
        self.assertNotIn("CNS-enriched", val, val)


class TestGtexSeamHonestDegradation(unittest.TestCase):

    def test_no_target_honest_empty(self):
        out = seam.findings({})
        self.assertEqual(out["facts"], [])
        self.assertEqual(out["provenance"], "gtex")
        self.assertNotIn("error", out)

    def test_blank_target_honest_empty(self):
        out = seam.findings({"candidate": "   "})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)

    def test_gene_not_found_is_honest_empty(self):
        """GTEx doesn't know the gene (reference returns no rows) → honest-empty,
        no error, and the expression endpoint is never called."""
        calls = []
        with mock.patch.object(seam, "_fetch", _dispatcher({"data": []}, None, calls)):
            out = seam.findings({"candidate": "NOTAGENE"})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)
        self.assertFalse([p for (path, p) in calls if "medianGeneExpression" in path],
                         "expression endpoint must not be called when gene unresolved")

    def test_no_expression_record_honest_empty(self):
        with mock.patch.object(seam, "_fetch", _dispatcher(_GENE_TSC2, {"data": []})):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)

    def test_transport_error_returns_envelope_never_raises(self):
        import urllib.error

        def _boom(path, params):
            raise urllib.error.URLError("connection refused")

        with mock.patch.object(seam, "_fetch", _boom):
            try:
                out = seam.findings({"candidate": "TSC2"})
            except Exception as exc:  # noqa: BLE001
                self.fail(f"findings() raised instead of degrading honestly: {exc!r}")
        self.assertEqual(out["facts"], [])
        self.assertIn("error", out)
        self.assertEqual(out["provenance"], "gtex")


@unittest.skipUnless(
    os.environ.get("SAPPHIRE_LIVE_TESTS") == "1",
    "live GTEx API test (set SAPPHIRE_LIVE_TESTS=1 to run; hits the public API, $0)",
)
class TestGtexSeamLive(unittest.TestCase):

    def test_live_tsc2_expression(self):
        out = seam.findings({"candidate": "TSC2"})
        if out.get("error"):
            self.skipTest(f"GTEx API unreachable: {out['error']}")
        self.assertEqual(len(out["facts"]), 1)
        val = out["facts"][0]["value"]
        self.assertIn("TSC2 GTEx tissue expression", val)
        self.assertIn("Brain", val)
        self.assertEqual(out["facts"][0]["tier"], "T1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
