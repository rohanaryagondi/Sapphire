"""Offline tests for the deterministic EMET DOM-scrape (emet/capture.py).

These exercise the PURE `parse_emet_html` path against saved HTML fixtures — **no live
browser, stdlib only** — so they run under the Gate-1 runner (plain `python`, no playwright).
The live capture (`capture_emet`) is verified by hand against the authenticated profile and
its rendered answer is saved as `fixtures/emet_tsc2_answer.html`, which the first test below
parses with the SAME logic that runs live.
"""
import json
import unittest
from pathlib import Path

from contracts.jsonschema_min import validate
from contracts.schemas import EMET_ENVELOPE_SCHEMA
from emet.capture import parse_emet_html, pick_workflow

FIX = Path(__file__).resolve().parent / "fixtures"


def _is_envelope(env: dict) -> bool:
    return not env.get("login_required") and "evidence" in env


class TestLoginAbstain(unittest.TestCase):
    def test_login_screen_html_abstains(self):
        html = (FIX / "emet_login_screen.html").read_text(encoding="utf-8")
        out = parse_emet_html(html, candidate="TSC2", query="anything")
        self.assertEqual(out, {"login_required": True})

    def test_login_host_with_signin_affordance_abstains(self):
        # The canonical login redirect host alongside a sign-in affordance and no answer article.
        html = ("<html><body><h1>Sign in</h1>"
                "<a href='https://id.summit.benchsci.com/'>Continue</a></body></html>")
        self.assertEqual(parse_emet_html(html, candidate="X"), {"login_required": True})

    def test_bare_auth_host_in_bundle_is_not_login(self):
        # The authenticated SPA references auth providers (auth0/okta) in its JS; a bare substring
        # must NOT be read as a login screen when a real answer <article> is present. (Regression:
        # the live TSC2 page contains 'auth0' twice yet is a fully-rendered answer.)
        html = ("<html><body><script>const idp='auth0';</script>"
                "<article><p>TSC2 evidence (PMID: 27226234).</p></article></body></html>")
        out = parse_emet_html(html, candidate="TSC2", query="x")
        self.assertFalse(out.get("login_required"))
        self.assertTrue(any(e["id_or_url"] == "PMID:27226234" for e in out["evidence"]))


class TestSyntheticAnswer(unittest.TestCase):
    """A minimal answer page exercising inline PubMed links, a printed PMID, a DOI, and the
    Sources panel — independent of the (large) live fixture."""

    HTML = """
    <html><body>
      <article>
        <p>TSC2 loss-of-function drives mTORC1 hyperactivation in tuberous sclerosis
           (PMID: 22426308). mTOR inhibitors reduce SEGA volume in TSC patients
           <a href="https://pubmed.ncbi.nlm.nih.gov/23158522/">[1]</a>.</p>
        <p>Everolimus is approved for TSC-associated SEGA; see doi.org link
           <a href="https://doi.org/10.1056/NEJMoa1001671">trial</a>.</p>
      </article>
      <aside aria-label="Sources">
        <button>Sources (3)</button>
        <ul>
          <li><a href="https://pubmed.ncbi.nlm.nih.gov/22426308/">Crino, NEJM 2006</a></li>
          <li><a href="https://pubmed.ncbi.nlm.nih.gov/23158522/">Franz, Lancet 2013</a></li>
          <li>Bissler et al. 2010 doi.org/10.1056/NEJMoa1001671</li>
        </ul>
      </aside>
    </body></html>
    """

    def test_extracts_expected_pmids_and_doi(self):
        env = parse_emet_html(self.HTML, candidate="TSC2",
                              query="Is TSC2 a viable CNS target in tuberous sclerosis?",
                              chat_url="https://emet.benchsci.com/chat/abc-123")
        self.assertTrue(_is_envelope(env))
        ids = {e["id_or_url"] for e in env["evidence"]}
        self.assertIn("PMID:22426308", ids)
        self.assertIn("PMID:23158522", ids)
        self.assertIn("10.1056/NEJMoa1001671", ids)

    def test_dedupes_ids(self):
        env = parse_emet_html(self.HTML, candidate="TSC2", query="x")
        ids = [e["id_or_url"] for e in env["evidence"]]
        self.assertEqual(len(ids), len(set(ids)), "evidence ids must be de-duplicated")

    def test_envelope_is_schema_valid(self):
        env = parse_emet_html(self.HTML, candidate="TSC2", query="x",
                              chat_url="https://emet.benchsci.com/chat/abc-123")
        errs = validate(env, EMET_ENVELOPE_SCHEMA)
        self.assertEqual(errs, [], f"schema errors: {errs}")
        self.assertEqual(env["provenance"], "emet-live")
        self.assertIn(env["emet_workflow"], {
            "Drug Safety", "Target Validation", "Pathway Analysis",
            "Quantitative Evidence", "Database Q&A"})

    def test_workflow_picker_is_deterministic(self):
        self.assertEqual(pick_workflow("DRD2", "what is the safety / adverse profile"), "Drug Safety")
        self.assertEqual(pick_workflow("TSC2", "is this a viable target for validation"),
                         "Target Validation")
        self.assertEqual(pick_workflow("X", "general prevalence question"), "Database Q&A")


class TestNoCitationsAbstainsHonestly(unittest.TestCase):
    def test_answer_with_no_ids_flags_not_fabricates(self):
        html = "<html><body><article><p>Insufficient evidence to assess this target.</p>" \
               "</article></body></html>"
        env = parse_emet_html(html, candidate="ZZZ1", query="x")
        self.assertTrue(_is_envelope(env))
        self.assertEqual(env["evidence"], [])      # NEVER fabricated
        self.assertEqual(env["verdict"], "flag")   # honest thin-evidence flag
        self.assertIn("no citable", env["notes"])


class TestLiveFixture(unittest.TestCase):
    """Parse the REAL captured TSC2 answer (saved by the live run) with the same logic."""

    def setUp(self):
        self.path = FIX / "emet_tsc2_answer.html"
        if not self.path.exists():
            self.skipTest("emet_tsc2_answer.html not captured (live run not yet performed)")

    def test_live_fixture_yields_valid_envelope_with_real_pmids(self):
        html = self.path.read_text(encoding="utf-8")
        env = parse_emet_html(html, candidate="TSC2",
                              query="Is TSC2 a viable CNS target in tuberous sclerosis? with PMIDs.",
                              chat_url="https://emet.benchsci.com/chat/live-fixture")
        self.assertTrue(_is_envelope(env), "live fixture should not be a login screen")
        errs = validate(env, EMET_ENVELOPE_SCHEMA)
        self.assertEqual(errs, [], f"schema errors: {errs}")
        pmids = [e["id_or_url"] for e in env["evidence"] if e["id_or_url"].startswith("PMID:")]
        self.assertGreaterEqual(len(pmids), 3,
                                f"expected >=3 real PMIDs scraped, got {pmids}")


if __name__ == "__main__":
    unittest.main()
