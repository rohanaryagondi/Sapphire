"""
tests/test_interpro_domains_seam.py — unit tests for the InterPro domains seam.

Offline/$0: the network is monkeypatched at the seam's single _fetch(url) boundary
with RECORDED responses (captured live on 2026-06-23 for TSC2 → UniProt P49815 →
InterPro). One guarded live test hits the real public APIs ($0); skips unless
SAPPHIRE_LIVE_TESTS=1.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_interpro_domains_seam -v
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

from tools import interpro_domains_seam as seam  # noqa: E402


# ── Recorded fixtures ─────────────────────────────────────────────────────────

_UNIPROT_TSC2 = {"results": [{"primaryAccession": "P49815"}]}

_INTERPRO_TSC2 = {"count": 8, "results": [
    {"metadata": {"accession": "IPR000331", "name": "Rap/Ran-GAP domain", "type": "domain"}},
    {"metadata": {"accession": "IPR003913", "name": "Tuberin", "type": "family"}},
    {"metadata": {"accession": "IPR011989", "name": "Armadillo-like helical", "type": "homologous_superfamily"}},
    {"metadata": {"accession": "IPR016024", "name": "Armadillo-type fold", "type": "homologous_superfamily"}},
    {"metadata": {"accession": "IPR018515", "name": "Tuberin-type domain", "type": "domain"}},
    {"metadata": {"accession": "IPR024584", "name": "Tuberin, N-terminal", "type": "domain"}},
    {"metadata": {"accession": "IPR027107", "name": "Tuberin/Ral GTPase-activating protein subunit alpha", "type": "family"}},
    {"metadata": {"accession": "IPR035974", "name": "Rap/Ran-GAP superfamily", "type": "homologous_superfamily"}},
]}

_UNIPROT_NONE = {"results": []}
_INTERPRO_EMPTY = {"count": 0, "results": []}

_INTERPRO_MANY_DOMAINS = {"count": 6, "results": [
    {"metadata": {"accession": f"IPR10000{i}", "name": f"Domain {i}", "type": "domain"}}
    for i in range(1, 7)
]}

_INTERPRO_ONLY_SF = {"count": 2, "results": [
    {"metadata": {"accession": "IPR011989", "name": "Armadillo-like helical", "type": "homologous_superfamily"}},
    {"metadata": {"accession": "IPR016024", "name": "Armadillo-type fold", "type": "homologous_superfamily"}},
]}


def _dispatch(uniprot_resp, interpro_resp, calls=None):
    def _f(url):
        if calls is not None:
            calls.append(url)
        if "rest.uniprot.org" in url:
            return uniprot_resp
        if "interpro" in url:
            return interpro_resp
        raise AssertionError(f"unexpected url {url}")
    return _f


class TestInterproSeamParsing(unittest.TestCase):

    def test_parses_tsc2_into_one_t1_fact(self):
        with mock.patch.object(seam, "_fetch", _dispatch(_UNIPROT_TSC2, _INTERPRO_TSC2)):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(out["candidate"], "TSC2")
        self.assertEqual(out["provenance"], "interpro")
        self.assertNotIn("error", out)
        self.assertEqual(len(out["facts"]), 1, out["facts"])
        val = out["facts"][0]["value"]
        self.assertIn("UniProt P49815", val, val)
        self.assertIn("8 entries", val, val)
        self.assertIn("domains:", val, val)
        self.assertIn("IPR000331", val, val)              # Rap/Ran-GAP domain accession
        self.assertIn("families:", val, val)
        self.assertIn("Tuberin (IPR003913)", val, val)
        self.assertEqual(out["facts"][0]["tier"], "T1")
        self.assertIn("InterPro", out["facts"][0]["source"])

    def test_fact_has_only_schema_allowed_keys(self):
        with mock.patch.object(seam, "_fetch", _dispatch(_UNIPROT_TSC2, _INTERPRO_TSC2)):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(set(out["facts"][0].keys()), {"value", "source", "tier"})

    def test_target_alias_accepted(self):
        with mock.patch.object(seam, "_fetch", _dispatch(_UNIPROT_TSC2, _INTERPRO_TSC2)):
            out = seam.findings({"target": "TSC2"})
        self.assertEqual(len(out["facts"]), 1)

    def test_resolved_accession_flows_to_interpro_url(self):
        """Two-call flow: the accession from UniProt is used in the InterPro URL."""
        calls = []
        with mock.patch.object(seam, "_fetch", _dispatch(_UNIPROT_TSC2, _INTERPRO_TSC2, calls)):
            seam.findings({"candidate": "TSC2"})
        interpro_calls = [u for u in calls if "interpro" in u]
        self.assertEqual(len(interpro_calls), 1, calls)
        self.assertIn("P49815", interpro_calls[0])

    def test_domain_overflow_is_capped(self):
        with mock.patch.object(seam, "_fetch", _dispatch(_UNIPROT_TSC2, _INTERPRO_MANY_DOMAINS)):
            out = seam.findings({"candidate": "SOMEGENE"})
        val = out["facts"][0]["value"]
        self.assertIn("+1 more", val, val)               # 6 domains, cap 5 → +1 more

    def test_only_superfamilies_reported_as_entry_types(self):
        with mock.patch.object(seam, "_fetch", _dispatch(_UNIPROT_TSC2, _INTERPRO_ONLY_SF)):
            out = seam.findings({"candidate": "SOMEGENE"})
        val = out["facts"][0]["value"]
        self.assertIn("entry types:", val, val)
        self.assertIn("homologous_superfamily", val, val)
        self.assertNotIn("domains:", val, val)


class TestInterproSeamHonestDegradation(unittest.TestCase):

    def test_no_target_honest_empty(self):
        out = seam.findings({})
        self.assertEqual(out["facts"], [])
        self.assertEqual(out["provenance"], "interpro")
        self.assertNotIn("error", out)

    def test_no_reviewed_protein_honest_empty(self):
        """UniProt has no reviewed human protein → honest-empty; InterPro not called."""
        calls = []
        with mock.patch.object(seam, "_fetch", _dispatch(_UNIPROT_NONE, None, calls)):
            out = seam.findings({"candidate": "NOTAGENE"})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)
        self.assertFalse([u for u in calls if "interpro" in u],
                         "InterPro must not be called when no accession resolves")

    def test_no_interpro_entries_honest_empty(self):
        with mock.patch.object(seam, "_fetch", _dispatch(_UNIPROT_TSC2, _INTERPRO_EMPTY)):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)

    def test_interpro_404_is_honest_empty(self):
        """A 404 from InterPro (no entries for the protein) is honest-empty, not error."""
        def _f(url):
            if "rest.uniprot.org" in url:
                return _UNIPROT_TSC2
            raise urllib.error.HTTPError(url, 404, "Not Found", None, None)

        with mock.patch.object(seam, "_fetch", _f):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(out["facts"], [])
        self.assertNotIn("error", out)

    def test_other_http_error_is_envelope(self):
        def _f(url):
            if "rest.uniprot.org" in url:
                return _UNIPROT_TSC2
            raise urllib.error.HTTPError(url, 500, "Server Error", None, None)

        with mock.patch.object(seam, "_fetch", _f):
            out = seam.findings({"candidate": "TSC2"})
        self.assertEqual(out["facts"], [])
        self.assertIn("error", out)

    def test_transport_error_returns_envelope_never_raises(self):
        def _boom(url):
            raise urllib.error.URLError("connection refused")

        with mock.patch.object(seam, "_fetch", _boom):
            try:
                out = seam.findings({"candidate": "TSC2"})
            except Exception as exc:  # noqa: BLE001
                self.fail(f"findings() raised instead of degrading honestly: {exc!r}")
        self.assertEqual(out["facts"], [])
        self.assertIn("error", out)
        self.assertEqual(out["provenance"], "interpro")


@unittest.skipUnless(
    os.environ.get("SAPPHIRE_LIVE_TESTS") == "1",
    "live InterPro/UniProt API test (set SAPPHIRE_LIVE_TESTS=1 to run; hits public APIs, $0)",
)
class TestInterproSeamLive(unittest.TestCase):

    def test_live_tsc2_domains(self):
        out = seam.findings({"candidate": "TSC2"})
        if out.get("error"):
            self.skipTest(f"InterPro/UniProt unreachable: {out['error']}")
        self.assertEqual(len(out["facts"]), 1)
        val = out["facts"][0]["value"]
        self.assertIn("UniProt P49815", val)
        self.assertIn("InterPro", val)
        self.assertIn("IPR", val)                         # at least one IPR accession
        self.assertEqual(out["facts"][0]["tier"], "T1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
