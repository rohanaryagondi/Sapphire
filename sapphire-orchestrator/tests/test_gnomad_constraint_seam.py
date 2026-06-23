"""
tests/test_gnomad_constraint_seam.py — unit tests for the gnomAD constraint seam.

All tests are offline/$0: the network is monkeypatched at the seam's single
_fetch() boundary with RECORDED gnomAD GraphQL responses (captured live from
https://gnomad.broadinstitute.org/api on 2026-06-23 for TSC2 and a bogus symbol).

One clearly-guarded live integration test hits the real public API ($0) and
skips cleanly when offline.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_gnomad_constraint_seam -v
"""
from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

# Ensure sapphire-orchestrator is on sys.path when running from repo root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ORCH_ROOT = os.path.dirname(_HERE)
if _ORCH_ROOT not in sys.path:
    sys.path.insert(0, _ORCH_ROOT)

from tools import gnomad_constraint_seam as seam  # noqa: E402


# ── Recorded fixtures (verbatim shapes returned by the live API) ──────────────

# TSC2: the GraphQL `data.gene.gnomad_constraint` payload (real values).
_FIXTURE_TSC2 = {
    "data": {
        "gene": {
            "symbol": "TSC2",
            "gnomad_constraint": {
                "pli": 1,
                "oe_lof": 0.14340755511655665,
                "oe_lof_upper": 0.1955335916011317,
                "mis_z": -0.07814465472993333,
            },
        }
    }
}

# Bogus symbol: gene not found — errors array + data.gene == null.
_FIXTURE_NOT_FOUND = {"errors": [{"message": "Gene not found"}], "data": {"gene": None}}

# Gene exists but has no constraint record (realistic for some genes).
_FIXTURE_NO_CONSTRAINT = {"data": {"gene": {"symbol": "FOO1", "gnomad_constraint": None}}}

# Constraint present but only pLI populated (the other metrics null).
_FIXTURE_PARTIAL = {
    "data": {"gene": {"symbol": "BAR1", "gnomad_constraint": {
        "pli": 0.93, "oe_lof": None, "oe_lof_upper": None, "mis_z": None}}}
}

# A tolerant gene: high LOEUF, low pLI — must NOT be called LoF-intolerant.
_FIXTURE_TOLERANT = {
    "data": {"gene": {"symbol": "TOL1", "gnomad_constraint": {
        "pli": 0.0, "oe_lof": 1.2, "oe_lof_upper": 1.45, "mis_z": 0.1}}}
}


class TestGnomadSeamParsing(unittest.TestCase):

    def test_parses_fixture_into_one_t1_fact(self):
        with mock.patch.object(seam, "_fetch", lambda symbol: _FIXTURE_TSC2):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(out["candidate"], "TSC2")
        self.assertEqual(out["provenance"], "gnomad")
        self.assertNotIn("error", out)
        self.assertEqual(len(out["facts"]), 1, f"expected exactly 1 fact; got {out['facts']}")
        fact = out["facts"][0]
        # Non-vacuous: the actual measured numbers must be in the value text.
        self.assertIn("pLI 1.00", fact["value"], fact["value"])
        self.assertIn("LOEUF 0.20", fact["value"], fact["value"])      # oe_lof_upper rounded
        self.assertIn("-0.08", fact["value"], fact["value"])           # mis_z rounded
        self.assertIn("loss-of-function intolerant", fact["value"], fact["value"])
        self.assertIn("TSC2", fact["value"])
        self.assertEqual(fact["tier"], "T1")
        self.assertIn("gnomAD", fact["source"])

    def test_fact_has_only_schema_allowed_keys(self):
        """The fact dict must carry exactly value/source/tier (no extra keys that
        the harness output_schema (additionalProperties:false) would reject)."""
        with mock.patch.object(seam, "_fetch", lambda symbol: _FIXTURE_TSC2):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(set(out["facts"][0].keys()), {"value", "source", "tier"})

    def test_target_alias_is_accepted(self):
        with mock.patch.object(seam, "_fetch", lambda symbol: _FIXTURE_TSC2):
            out = seam.findings({"target": "TSC2"})
        self.assertEqual(len(out["facts"]), 1)
        self.assertEqual(out["candidate"], "TSC2")

    def test_partial_constraint_still_builds_fact(self):
        with mock.patch.object(seam, "_fetch", lambda symbol: _FIXTURE_PARTIAL):
            out = seam.findings({"candidate": "BAR1"})
        self.assertEqual(len(out["facts"]), 1)
        val = out["facts"][0]["value"]
        self.assertIn("pLI 0.93", val, val)
        self.assertNotIn("LOEUF", val, val)        # null LOEUF omitted, not fabricated
        self.assertIn("loss-of-function intolerant", val)  # pLI 0.93 >= 0.9

    def test_tolerant_gene_not_overclaimed(self):
        with mock.patch.object(seam, "_fetch", lambda symbol: _FIXTURE_TOLERANT):
            out = seam.findings({"candidate": "TOL1"})
        self.assertEqual(len(out["facts"]), 1)
        val = out["facts"][0]["value"]
        self.assertNotIn("intolerant", val, f"tolerant gene must not be called intolerant: {val}")
        self.assertIn("LOEUF 1.45", val, val)


class TestGnomadSeamHonestDegradation(unittest.TestCase):

    def test_no_target_honest_empty(self):
        out = seam.findings({})
        self.assertEqual(out["facts"], [])
        self.assertEqual(out["provenance"], "gnomad")
        self.assertNotIn("error", out)

    def test_blank_target_honest_empty(self):
        out = seam.findings({"candidate": "   "})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)

    def test_gene_not_found_is_honest_empty_not_error(self):
        """gene == null (not found) is a known-unknown, not a backend failure:
        facts=[] with NO error envelope."""
        with mock.patch.object(seam, "_fetch", lambda symbol: _FIXTURE_NOT_FOUND):
            out = seam.findings({"candidate": "ZZZNOTAGENE1"})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)

    def test_no_constraint_record_honest_empty(self):
        with mock.patch.object(seam, "_fetch", lambda symbol: _FIXTURE_NO_CONSTRAINT):
            out = seam.findings({"candidate": "FOO1"})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)

    def test_transport_error_returns_envelope_never_raises(self):
        import urllib.error

        def _boom(symbol):
            raise urllib.error.URLError("connection refused")

        with mock.patch.object(seam, "_fetch", _boom):
            try:
                out = seam.findings({"candidate": "TSC2"})
            except Exception as exc:  # noqa: BLE001
                self.fail(f"findings() raised instead of degrading honestly: {exc!r}")
        self.assertEqual(out["facts"], [])
        self.assertIn("error", out)
        self.assertEqual(out["provenance"], "gnomad")

    def test_graphql_error_without_data_is_error_envelope(self):
        """A GraphQL failure with no data payload is surfaced as an honest error,
        distinct from a gene-not-found honest-empty."""
        with mock.patch.object(seam, "_fetch", lambda symbol: {"errors": [{"message": "boom"}]}):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(out["facts"], [])
        self.assertIn("error", out)


@unittest.skipUnless(
    os.environ.get("SAPPHIRE_LIVE_TESTS") == "1",
    "live gnomAD API test (set SAPPHIRE_LIVE_TESTS=1 to run; hits the public API, $0)",
)
class TestGnomadSeamLive(unittest.TestCase):
    """Hits the REAL public gnomAD API. Opt-in via SAPPHIRE_LIVE_TESTS=1; skips
    cleanly (returns honest error envelope) if the network is unavailable."""

    def test_live_tsc2_constraint(self):
        out = seam.findings({"candidate": "TSC2"})
        if out.get("error"):
            self.skipTest(f"gnomAD API unreachable: {out['error']}")
        self.assertEqual(len(out["facts"]), 1)
        val = out["facts"][0]["value"]
        self.assertIn("pLI", val)
        self.assertIn("LOEUF", val)
        self.assertEqual(out["facts"][0]["tier"], "T1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
