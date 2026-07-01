"""Hermetic tests for the EMET FILE-BRIDGE handler (WO-9). NO real browser, NO real clock.

Covers: a pre-written responses.jsonl → cited T2 facts; error/empty/blank → honest abstain
(empty facts, never fabricated); a timeout → honest abstain (bounded, never hangs); the request
line is appended in the protocol shape (public identifiers only); env-gate OFF keeps the old
Playwright path in live_engine._wire_emet_handler; and the provenance label is registered.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import emet.bridge_handler as B
from emet.bridge_handler import make_emet_bridge_handler, PROVENANCE
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

    def test_request_line_appended_in_protocol_shape_public_only(self):
        planted = {}
        real_append = B._append_request

        def _spy_append(path, req):
            planted["req"] = req
            real_append(path, req)
            _write_responses(self._dir, [{"id": req["id"], "status": "empty",
                                          "evidence": "", "citations": [], "ts": "t"}])

        with mock.patch.object(B, "_append_request", _spy_append):
            h = make_emet_bridge_handler(sleep=lambda _s: None)
            h(C, {"candidate": "TSC2", "question": "Is TSC2 a viable target?"})

        req = planted["req"]
        self.assertEqual(set(req.keys()), {"id", "query", "gene", "ts"})
        self.assertEqual(req["gene"], "TSC2")               # public identifier only
        self.assertIn("TSC2", req["query"])
        # the request file actually holds the appended line
        lines = (self._dir / "requests.jsonl").read_text().strip().splitlines()
        self.assertEqual(json.loads(lines[-1])["id"], req["id"])


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


class TestBridgeConfig(_BridgeCase):
    def test_timeout_default_and_override_and_floor(self):
        self.assertEqual(B._timeout_s(), 180)               # default
        os.environ["SAPPHIRE_EMET_BRIDGE_TIMEOUT_S"] = "90"
        self.assertEqual(B._timeout_s(), 90)
        os.environ["SAPPHIRE_EMET_BRIDGE_TIMEOUT_S"] = "1"
        self.assertEqual(B._timeout_s(), 5)                 # floored
        os.environ["SAPPHIRE_EMET_BRIDGE_TIMEOUT_S"] = "junk"
        self.assertEqual(B._timeout_s(), 180)               # bad → default

    def test_provenance_label_registered_external_plane(self):
        self.assertTrue(is_valid_provenance("emet-live-bridge"))
        self.assertEqual(plane_for("emet-live-bridge"), "external")


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
