"""Hermetic tests for the EMET FILE-BRIDGE handler (WO-9 + comprehensive multi-source).
NO real browser, NO real clock.

Covers:
  - a pre-written responses.jsonl → cited T2 facts (full evidence untruncated)
  - error/empty/blank → honest abstain (empty facts, never fabricated)
  - timeout → honest abstain (bounded, never hangs)
  - request line appended in protocol shape (public identifiers only, genes[] present)
  - env-gate OFF keeps the old Playwright path in live_engine._wire_emet_handler
  - provenance label is registered
  - COMPREHENSIVE MULTI-SOURCE QUERY: build_emet_query mentions GTEx / gnomAD / ClinVar /
    Reactome / STRING / ClinicalTrials.gov / MGI — not just BenchSci literature
  - SCALING TIMEOUT: formula base + per_pending × (unanswered−1), capped at 3600s
  - MULTI-GENE BATCHING: a multi-gene inputs dict emits ONE request covering all genes
  - DEFAULT TIMEOUT is now 900s (was 180)
  - FULL EVIDENCE PASSTHROUGH: the entire evidence body passes through untruncated
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import emet.bridge_handler as B
from emet.bridge_handler import (
    make_emet_bridge_handler, build_emet_query, PROVENANCE,
    _timeout_s, _scaled_timeout_s, _count_unanswered, _gene_list,
    _PER_PENDING_S, _TIMEOUT_CAP_S,
)
from harness.contracts import Contract
from contracts.provenance import is_valid_provenance, plane_for

C = Contract(id="emet-runner", role="", kind="emet-playwright",
             provenance_label="emet-live-bridge")


def _write_responses(d: Path, lines):
    (d / "responses.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in lines), encoding="utf-8")


class _BridgeCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._dir = Path(self._tmp.name)
        self._saved = {k: os.environ.pop(k, None) for k in
                       ("SAPPHIRE_EMET_BRIDGE_DIR", "SAPPHIRE_EMET_BRIDGE_TIMEOUT_S",
                        "SAPPHIRE_EMET_BRIDGE_POLL_S", "SAPPHIRE_EMET_BRIDGE")}
        os.environ["SAPPHIRE_EMET_BRIDGE_DIR"] = str(self._dir)

    def tearDown(self):
        for k in ("SAPPHIRE_EMET_BRIDGE_DIR", "SAPPHIRE_EMET_BRIDGE_TIMEOUT_S",
                  "SAPPHIRE_EMET_BRIDGE_POLL_S", "SAPPHIRE_EMET_BRIDGE"):
            os.environ.pop(k, None)
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v
        self._tmp.cleanup()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestBridgeHappyPath(_BridgeCase):
    def test_prewritten_ok_response_returns_cited_t2_facts(self):
        # The peer session has already answered id-... — but the handler generates its own uuid,
        # so we intercept the request to learn the id, then plant the matching response.
        planted = {}
        real_append = B._append_request

        def _spy_append(path, req):
            planted["id"] = req["id"]
            planted["req"] = req
            real_append(path, req)
            _write_responses(self._dir, [{
                "id": req["id"], "status": "ok",
                "evidence": "SCN9A GoF causes inherited erythromelalgia (T2 evidence).",
                "citations": ["PMID:15385606", "DOI:10.1/x"], "ts": "t"}])

        with mock.patch.object(B, "_append_request", _spy_append):
            h = make_emet_bridge_handler(sleep=lambda _s: None)
            out = h(C, {"candidate": "SCN9A", "question": "validate target"})

        self.assertEqual(out["candidate"], "SCN9A")
        self.assertEqual(out["provenance"], PROVENANCE)
        # evidence markdown + 2 citations = 3 cited T2 facts, all bridge-provenance
        self.assertEqual(len(out["facts"]), 3)
        for f in out["facts"]:
            self.assertEqual(f["tier"], "T2")
            self.assertEqual(f["provenance"], PROVENANCE)
        self.assertIn("erythromelalgia", out["facts"][0]["value"])
        self.assertEqual(out["facts"][1]["source"], "PMID:15385606")

    def test_request_line_appended_in_protocol_shape_with_genes(self):
        """Request shape must carry id, query, gene, genes, ts — and genes[] must be present."""
        planted = {}
        real_append = B._append_request

        def _spy_append(path, req):
            planted["req"] = req
            real_append(path, req)
            _write_responses(self._dir, [{"id": req["id"], "status": "empty",
                                          "evidence": "", "citations": [], "ts": "t"}])

        with mock.patch.object(B, "_append_request", _spy_append):
            h = make_emet_bridge_handler(sleep=lambda _s: None)
            h(C, {"candidate": "TSC2", "query": "Is TSC2 a viable target?"})

        req = planted["req"]
        # genes[] is now required in the protocol shape
        self.assertIn("genes", req)
        self.assertIn("gene", req)
        self.assertIn("query", req)
        self.assertIn("id", req)
        self.assertIn("ts", req)
        self.assertEqual(req["gene"], "TSC2")               # public identifier only
        self.assertIn("TSC2", req["query"])
        # the request file actually holds the appended line
        lines = (self._dir / "requests.jsonl").read_text().strip().splitlines()
        self.assertEqual(json.loads(lines[-1])["id"], req["id"])

    def test_full_evidence_passes_through_untruncated(self):
        """The full evidence body must pass through — no truncation anywhere in the pipeline."""
        long_evidence = ("A" * 200 + "\n\n" + "B" * 200 + "\n\nSupporting detail: " + "C" * 500)
        real_append = B._append_request

        def _spy_append(path, req):
            real_append(path, req)
            _write_responses(self._dir, [{
                "id": req["id"], "status": "ok",
                "evidence": long_evidence,
                "citations": ["PMID:99999"], "ts": "t"}])

        with mock.patch.object(B, "_append_request", _spy_append):
            h = make_emet_bridge_handler(sleep=lambda _s: None)
            out = h(C, {"candidate": "GENE1", "query": "long evidence test"})

        self.assertEqual(len(out["facts"]), 2)
        # The FULL evidence must be present — not truncated
        self.assertEqual(out["facts"][0]["value"], long_evidence)


# ---------------------------------------------------------------------------
# Abstain / error cases
# ---------------------------------------------------------------------------

class TestBridgeAbstain(_BridgeCase):
    def _run_with_response(self, resp_line):
        real_append = B._append_request

        def _spy_append(path, req):
            real_append(path, req)
            _write_responses(self._dir, [{**resp_line, "id": req["id"]}])

        with mock.patch.object(B, "_append_request", _spy_append):
            h = make_emet_bridge_handler(sleep=lambda _s: None)
            return h(C, {"candidate": "GENEX", "question": "q"})

    def test_status_error_is_honest_abstain(self):
        out = self._run_with_response({"status": "error", "evidence": "boom", "citations": []})
        self.assertEqual(out["facts"], [])                  # NO fabricated facts
        self.assertEqual(out["provenance"], PROVENANCE)
        self.assertEqual(out["candidate"], "GENEX")

    def test_status_empty_is_honest_abstain(self):
        out = self._run_with_response({"status": "empty", "evidence": "", "citations": []})
        self.assertEqual(out["facts"], [])

    def test_ok_but_blank_evidence_is_honest_abstain(self):
        # status ok but no evidence body → nothing to cite → honest abstain, not a blank fact.
        out = self._run_with_response({"status": "ok", "evidence": "   ", "citations": ["PMID:1"]})
        self.assertEqual(out["facts"], [])

    def test_timeout_is_bounded_honest_abstain(self):
        # No response is ever planted → the handler must time out and abstain (never hang).
        os.environ["SAPPHIRE_EMET_BRIDGE_TIMEOUT_S"] = "30"
        os.environ["SAPPHIRE_EMET_BRIDGE_POLL_S"] = "2"
        ticks = iter([0.0, 10.0, 20.0, 40.0])   # 4th read is past the 30s deadline
        slept = []
        h = make_emet_bridge_handler(sleep=lambda s: slept.append(s),
                                     clock=lambda: next(ticks))
        out = h(C, {"candidate": "NORSP", "question": "q"})
        self.assertEqual(out["facts"], [])                  # honest abstain on timeout
        self.assertEqual(out["provenance"], PROVENANCE)
        self.assertTrue(slept)                              # it actually polled (didn't hang)

    def test_handler_never_raises_on_io_error(self):
        # A filesystem explosion inside the poll must degrade to abstain, never propagate.
        with mock.patch.object(B, "_append_request", side_effect=OSError("disk gone")):
            h = make_emet_bridge_handler(sleep=lambda _s: None)
            out = h(C, {"candidate": "IOERR"})
        self.assertEqual(out["facts"], [])
        self.assertEqual(out["candidate"], "IOERR")


# ---------------------------------------------------------------------------
# Malformed response lines
# ---------------------------------------------------------------------------

class TestBridgeMalformedResponseLines(_BridgeCase):
    def test_malformed_lines_are_skipped_not_crashing(self):
        real_append = B._append_request

        def _spy_append(path, req):
            real_append(path, req)
            # a junk line, a non-matching line, then the real matching one
            (self._dir / "responses.jsonl").write_text(
                "not json\n"
                + json.dumps({"id": "other", "status": "ok", "evidence": "x"}) + "\n"
                + json.dumps({"id": req["id"], "status": "ok",
                              "evidence": "real evidence", "citations": []}) + "\n",
                encoding="utf-8")

        with mock.patch.object(B, "_append_request", _spy_append):
            h = make_emet_bridge_handler(sleep=lambda _s: None)
            out = h(C, {"candidate": "SCN2A"})
        self.assertEqual(len(out["facts"]), 1)
        self.assertIn("real evidence", out["facts"][0]["value"])


# ---------------------------------------------------------------------------
# Config (timeout defaults + provenance)
# ---------------------------------------------------------------------------

class TestBridgeConfig(_BridgeCase):
    def test_default_timeout_is_900(self):
        """Default timeout changed from 180 to 900 (15 min) for multi-source EMET sweeps."""
        self.assertEqual(_timeout_s(), 900)

    def test_timeout_override_and_floor(self):
        os.environ["SAPPHIRE_EMET_BRIDGE_TIMEOUT_S"] = "90"
        self.assertEqual(_timeout_s(), 90)
        os.environ["SAPPHIRE_EMET_BRIDGE_TIMEOUT_S"] = "1"
        self.assertEqual(_timeout_s(), 5)                 # floored
        os.environ["SAPPHIRE_EMET_BRIDGE_TIMEOUT_S"] = "junk"
        self.assertEqual(_timeout_s(), 900)               # bad → new default (900)

    def test_provenance_label_registered_external_plane(self):
        self.assertTrue(is_valid_provenance("emet-live-bridge"))
        self.assertEqual(plane_for("emet-live-bridge"), "external")


# ---------------------------------------------------------------------------
# COMPREHENSIVE MULTI-SOURCE QUERY (new in WO-9 update)
# ---------------------------------------------------------------------------

class TestComprehensiveMultiSourceQuery(unittest.TestCase):
    """build_emet_query must instruct the worker to use non-literature sources."""

    def test_query_mentions_gtex(self):
        q = build_emet_query({"candidate": "SCN9A", "query": "CNS target assessment"})
        self.assertIn("GTEx", q)

    def test_query_mentions_gnomad(self):
        q = build_emet_query({"candidate": "TSC2", "disease": "tuberous sclerosis"})
        self.assertIn("gnomAD", q)

    def test_query_mentions_clinvar(self):
        q = build_emet_query({"candidate": "TSC2"})
        self.assertIn("ClinVar", q)

    def test_query_mentions_reactome_or_kegg(self):
        q = build_emet_query({"candidate": "TSC2"})
        self.assertTrue("Reactome" in q or "KEGG" in q, f"Expected Reactome or KEGG in: {q[:200]}")

    def test_query_mentions_clinicaltrials(self):
        q = build_emet_query({"candidate": "SCN9A"})
        self.assertIn("ClinicalTrials", q)

    def test_query_mentions_mgi_or_impc(self):
        q = build_emet_query({"candidate": "SCN9A"})
        self.assertTrue("MGI" in q or "IMPC" in q, f"Expected MGI or IMPC in: {q[:200]}")

    def test_query_asks_for_evidence_for_and_against(self):
        q = build_emet_query({"candidate": "NAV1.8", "disease": "pain"})
        # Must ask for BOTH supporting and negative evidence
        self.assertIn("FOR", q)
        self.assertIn("AGAINST", q)

    def test_query_includes_candidate_and_disease(self):
        q = build_emet_query({"candidate": "TSC2", "disease": "tuberous sclerosis",
                              "query": "Is TSC2 viable?"})
        self.assertIn("TSC2", q)
        self.assertIn("tuberous sclerosis", q)

    def test_query_enforces_data_boundary_note(self):
        q = build_emet_query({"candidate": "TSC2"})
        # Must mention the public-identifiers-only rule
        self.assertIn("public", q.lower())

    def test_empty_inputs_returns_empty_string(self):
        q = build_emet_query({})
        self.assertEqual(q, "")

    def test_query_text_from_question_field(self):
        q = build_emet_query({"candidate": "KCNQ2", "question": "neonatal seizures"})
        self.assertIn("KCNQ2", q)
        self.assertIn("neonatal", q)


# ---------------------------------------------------------------------------
# SCALING TIMEOUT (new in WO-9 update)
# ---------------------------------------------------------------------------

class TestScalingTimeout(unittest.TestCase):
    """_scaled_timeout_s must follow: min(base + per_pending × (unanswered−1), cap)."""

    def _make_queue(self, tmp: Path, n_req: int, n_answered: int):
        """Write n_req requests with n_answered responses, return (requests_path, responses_path)."""
        req_ids = [str(i) for i in range(n_req)]
        req_path = tmp / "requests.jsonl"
        resp_path = tmp / "responses.jsonl"
        with req_path.open("w") as f:
            for rid in req_ids:
                f.write(json.dumps({"id": rid, "query": "q", "gene": "G", "genes": ["G"],
                                    "ts": "t"}) + "\n")
        with resp_path.open("w") as f:
            for rid in req_ids[:n_answered]:
                f.write(json.dumps({"id": rid, "status": "ok", "evidence": "e",
                                    "citations": []}) + "\n")
        return req_path, resp_path

    def test_single_pending_uses_base_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            req_path, resp_path = self._make_queue(p, 1, 0)
            # 1 unanswered → extra = per_pending × (1−1) = 0 → base
            result = _scaled_timeout_s(req_path, resp_path)
            base = _timeout_s()
            self.assertEqual(result, base)

    def test_two_unanswered_adds_per_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            req_path, resp_path = self._make_queue(p, 2, 0)
            # 2 unanswered → extra = _PER_PENDING_S × 1
            result = _scaled_timeout_s(req_path, resp_path)
            expected = min(_timeout_s() + _PER_PENDING_S, _TIMEOUT_CAP_S)
            self.assertEqual(result, expected)

    def test_many_unanswered_capped_at_3600(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            # 50 unanswered requests: base(900) + 49 × 120 = 6780 → capped at 3600
            req_path, resp_path = self._make_queue(p, 50, 0)
            result = _scaled_timeout_s(req_path, resp_path)
            self.assertEqual(result, _TIMEOUT_CAP_S)

    def test_answered_requests_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            # 5 requests, 4 answered → 1 unanswered → base only
            req_path, resp_path = self._make_queue(p, 5, 4)
            result = _scaled_timeout_s(req_path, resp_path)
            self.assertEqual(result, _timeout_s())

    def test_missing_files_returns_base_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            # Neither file exists → _count_unanswered returns 1 → base
            result = _scaled_timeout_s(p / "req.jsonl", p / "resp.jsonl")
            self.assertEqual(result, _timeout_s())

    def test_cap_constant_is_3600(self):
        self.assertEqual(_TIMEOUT_CAP_S, 3600)

    def test_per_pending_constant_is_120(self):
        self.assertEqual(_PER_PENDING_S, 120)


# ---------------------------------------------------------------------------
# MULTI-GENE BATCHING (new in WO-9 update)
# ---------------------------------------------------------------------------

class TestMultiGeneBatching(_BridgeCase):
    """A multi-gene inputs dict must produce ONE batched request covering all genes — not
    one request per gene. The emet-runner is called once per engagement, so a single call
    with genes=[G1, G2, G3] must produce one request with all three genes in the query."""

    def test_multi_gene_single_request_covers_all_genes(self):
        """When genes=[TSC1, TSC2, RHEB] arrive in inputs, ONE request must name all three."""
        planted = []
        real_append = B._append_request

        def _spy_append(path, req):
            planted.append(req)
            real_append(path, req)
            # Pre-write the response so the handler doesn't block.
            _write_responses(self._dir, [{
                "id": req["id"], "status": "ok",
                "evidence": "TSC1/TSC2/RHEB pathway evidence.",
                "citations": ["PMID:11111"], "ts": "t"}])

        inputs = {
            "candidate": "TSC1",
            "genes": ["TSC1", "TSC2", "RHEB"],
            "disease": "tuberous sclerosis",
            "query": "Compare TSC1, TSC2, RHEB as targets",
        }

        with mock.patch.object(B, "_append_request", _spy_append):
            h = make_emet_bridge_handler(sleep=lambda _s: None)
            out = h(C, inputs)

        # Exactly ONE request must have been written (batched, not one per gene).
        self.assertEqual(len(planted), 1, "Expected exactly one batched request for multi-gene")
        req = planted[0]

        # The query must mention all three genes.
        self.assertIn("TSC1", req["query"])
        self.assertIn("TSC2", req["query"])
        self.assertIn("RHEB", req["query"])

        # The genes[] list must carry all three.
        self.assertCountEqual(req["genes"], ["TSC1", "TSC2", "RHEB"])

        # The response facts must land in the output.
        self.assertGreater(len(out["facts"]), 0)

    def test_multi_gene_query_contains_all_gene_count_note(self):
        """build_emet_query must note the multi-gene scope so the worker surveys all targets."""
        inputs = {"candidate": "TSC1", "genes": ["TSC1", "TSC2", "RHEB"],
                  "query": "Compare targets"}
        q = build_emet_query(inputs)
        # The query must say it's a multi-gene (batched) request.
        self.assertIn("MULTI-GENE", q.upper().replace("-", "").replace("_", "")
                      .replace("MULTIGENE", "MULTIGENE").replace("MULTI GENE", "MULTIGENE")
                      .replace("multi-gene", "MULTIGENE")
                      if "MULTI" not in q.upper() else q.upper())
        # All three genes in the query
        self.assertIn("TSC1", q)
        self.assertIn("TSC2", q)
        self.assertIn("RHEB", q)

    def test_gene_list_deduplicates(self):
        """Duplicate gene symbols in inputs["genes"] must be deduplicated."""
        genes = _gene_list({"genes": ["TSC2", "TSC2", "TSC1", "TSC2"]})
        self.assertEqual(genes, ["TSC2", "TSC1"])

    def test_gene_list_fallback_to_candidate(self):
        """When inputs has no genes[] key, fall back to the candidate."""
        genes = _gene_list({"candidate": "SCN9A"})
        self.assertEqual(genes, ["SCN9A"])

    def test_gene_list_empty_when_no_identifiers(self):
        genes = _gene_list({})
        self.assertEqual(genes, [])


# ---------------------------------------------------------------------------
# Env-gate (live_engine wiring)
# ---------------------------------------------------------------------------

class TestWireEmetHandlerGate(unittest.TestCase):
    """Env-gate: SAPPHIRE_EMET_BRIDGE=1 installs the bridge handler; default OFF keeps the
    existing Playwright-runner path; a caller-supplied handler always wins."""

    def setUp(self):
        self._prev = os.environ.pop("SAPPHIRE_EMET_BRIDGE", None)

    def tearDown(self):
        os.environ.pop("SAPPHIRE_EMET_BRIDGE", None)
        if self._prev is not None:
            os.environ["SAPPHIRE_EMET_BRIDGE"] = self._prev

    def test_gate_off_uses_existing_playwright_handler(self):
        import live_engine
        ctx = {}
        live_engine._wire_emet_handler(ctx)
        self.assertIn("emet_handler", ctx)
        # The default (Playwright) handler is emet.handler.make_emet_handler's closure, defined in
        # emet.handler — NOT the bridge module.
        self.assertEqual(ctx["emet_handler"].__module__, "emet.handler")

    def test_gate_on_installs_bridge_handler(self):
        import live_engine
        os.environ["SAPPHIRE_EMET_BRIDGE"] = "1"
        ctx = {}
        live_engine._wire_emet_handler(ctx)
        self.assertEqual(ctx["emet_handler"].__module__, "emet.bridge_handler")

    def test_caller_supplied_handler_wins_even_with_gate_on(self):
        import live_engine
        os.environ["SAPPHIRE_EMET_BRIDGE"] = "1"
        sentinel = lambda contract, inputs: {"candidate": "x", "facts": []}
        ctx = {"emet_handler": sentinel}
        live_engine._wire_emet_handler(ctx)
        self.assertIs(ctx["emet_handler"], sentinel)        # setdefault semantics preserved


if __name__ == "__main__":
    unittest.main()
