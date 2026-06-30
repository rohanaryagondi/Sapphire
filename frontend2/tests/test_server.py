"""Offline tests for frontend2/server.py — the stdlib-only SSE front-end server.

All tests run with profile=="demo" (the offline mock ctx): $0, no network, deterministic.
They exercise the real server over a real socket (a background ThreadingHTTPServer on an
ephemeral port) so the SSE wire format + streaming are tested end-to-end, not mocked.

Engagement/memory writes are isolated to temp dirs so the suite never touches real state.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]          # frontend2/
_REPO = _HERE.parent
for _p in (str(_HERE), str(_REPO / "frontend"), str(_REPO / "sapphire-orchestrator")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import server  # noqa: E402  (frontend2/server.py)


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _parse_sse(text: str) -> list:
    """Parse a raw SSE response body → [(event, data_obj), …]."""
    out = []
    for frame in text.split("\n\n"):
        frame = frame.strip("\n")
        if not frame:
            continue
        event, data_lines = None, []
        for line in frame.split("\n"):
            if line.startswith("event:"):
                event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].lstrip(" "))
        data = None
        if data_lines:
            try:
                data = json.loads("\n".join(data_lines))
            except Exception:
                data = "\n".join(data_lines)
        if event:
            out.append((event, data))
    return out


class _ServerHarness:
    """Boot the real Handler on an ephemeral port in a background thread."""

    def __enter__(self):
        self.port = _free_port()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), server.Handler)
        self.t = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.t.start()
        self.base = f"http://127.0.0.1:{self.port}"
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.t.join(timeout=2.0)

    def post_run(self, body: dict, timeout: float = 60.0) -> str:
        req = urllib.request.Request(
            self.base + "/api/run",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")

    def get(self, path: str, timeout: float = 10.0):
        with urllib.request.urlopen(self.base + path, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8"), resp.headers

    def post_json(self, path: str, body: dict, timeout: float = 10.0):
        """POST a JSON body and return (status, body_text, headers)."""
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8"), resp.headers


class TestServer(unittest.TestCase):
    def setUp(self):
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = tempfile.mkdtemp()
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    # ---- the core contract: progress events + a result dossier -----------
    def test_run_streams_progress_then_result(self):
        with _ServerHarness() as h:
            raw = h.post_run({"query": "Is TSC2 a viable target in tuberous sclerosis?",
                              "profile": "demo"})
        events = _parse_sse(raw)
        kinds = [e for e, _ in events]
        # An `open` first, at least one `progress`, exactly one `result`, a final `done`.
        self.assertEqual(kinds[0], "open")
        self.assertEqual(kinds[-1], "done")
        self.assertIn("result", kinds)
        progresses = [d for e, d in events if e == "progress"]
        self.assertTrue(progresses, "must stream at least one progress event")
        # The progress events cover the firm's stages.
        stages = {p["stage"] for p in progresses}
        self.assertEqual(stages, {"plan", "bucket1", "flags", "roundtable", "synthesis"})

    def test_result_is_a_valid_run_live_dossier(self):
        from contracts.run_live_schema import validate_run_live
        from moat.client import MoatClient
        with _ServerHarness() as h:
            raw = h.post_run({"query": "Is TSC2 a viable target in tuberous sclerosis?",
                              "profile": "demo"})
        events = _parse_sse(raw)
        results = [d for e, d in events if e == "result"]
        self.assertEqual(len(results), 1)
        result = results[0]
        # The streamed result conforms to the documented run_live contract (additive keys ok).
        self.assertEqual(validate_run_live(result), [])
        # Real dossier content lands: a roundtable spread, a synthesis, and a non-empty dossier.
        dossier = result["discover"]["dossier"]
        self.assertTrue(dossier)
        planes = {f.get("plane") for f in dossier}
        self.assertIn("external", planes)
        # The internal-plane assertion needs the real Loka moat DB (gitignored,
        # not present on every machine); the product behavior degrades to
        # empty/mock HONESTLY without it (per CLAUDE.md). Mirrors the same
        # MoatClient().available() guard used by
        # tests/test_live_engine.py::test_moat_real_provenance — see dev/HELP.md
        # (this was the one remaining unconditional "internal" assertion it
        # flagged).
        if MoatClient().available():
            self.assertIn("internal", planes)
        else:
            print(
                "  [skip] internal-plane assertion: RohanOnly/moat/moat.sqlite "
                "not built — see dev/HELP.md (moat-db-test-skipguards)"
            )
        self.assertTrue(result["consult"]["round1"])
        self.assertTrue(result["synthesize"]["recommendation"])
        self.assertEqual(result["_via"], "harness-live")

    def test_progress_done_events_carry_honest_status(self):
        """A done bucket1/roundtable event carries the REAL status/provenance — the UI marks
        an abstain as an abstain (⚠), never a false ✓. Assert the fields exist + are honest."""
        with _ServerHarness() as h:
            raw = h.post_run({"query": "Is TSC2 a viable target in tuberous sclerosis?",
                              "profile": "demo"})
        events = _parse_sse(raw)
        done_b1 = [d for e, d in events if e == "progress"
                   and d.get("stage") == "bucket1" and d.get("phase") == "done"]
        self.assertTrue(done_b1)
        for d in done_b1:
            self.assertIn("status", d)
            self.assertIn("provenance", d)
            self.assertIn(d["status"], ("ok", "abstained", "escalated"))

    # ---- input handling --------------------------------------------------
    def test_empty_query_rejected(self):
        with _ServerHarness() as h:
            try:
                h.post_run({"query": "", "profile": "demo"})
                self.fail("empty query should be rejected")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 400)

    def test_invalid_json_body_rejected(self):
        with _ServerHarness() as h:
            req = urllib.request.Request(
                h.base + "/api/run", data=b"{not json",
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                urllib.request.urlopen(req, timeout=10)
                self.fail("invalid JSON should be rejected")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 400)

    # ---- honest-degrade: a worker exception → an error frame, then done --
    def test_bridge_failure_degrades_to_error_frame_not_500(self):
        """If the run path raises (we monkeypatch bridge.run to blow up), the stream must
        still return 200 + an `error` event + a final `done` — never a 500/crash."""
        orig = server.bridge.run

        def _boom(*a, **k):
            raise RuntimeError("simulated backend failure")

        server.bridge.run = _boom
        try:
            with _ServerHarness() as h:
                raw = h.post_run({"query": "anything", "profile": "demo"})
        finally:
            server.bridge.run = orig
        events = _parse_sse(raw)
        kinds = [e for e, _ in events]
        self.assertIn("error", kinds)              # honest error, not a fabricated answer
        self.assertEqual(kinds[-1], "done")        # stream still closes cleanly
        err = [d for e, d in events if e == "error"][0]
        self.assertIn("simulated backend failure", err["error"])

    # ---- static + replays ------------------------------------------------
    def test_index_served_at_root(self):
        with _ServerHarness() as h:
            status, body, headers = h.get("/")
        self.assertEqual(status, 200)
        self.assertIn("Sapphire", body)
        self.assertIn("text/html", headers.get("Content-Type", ""))

    def test_static_path_traversal_blocked(self):
        with _ServerHarness() as h:
            try:
                h.get("/static/../server.py")
                self.fail("path traversal should be blocked")
            except urllib.error.HTTPError as e:
                self.assertIn(e.code, (403, 404))

    def test_replays_endpoint(self):
        with _ServerHarness() as h:
            status, body, _ = h.get("/api/replays")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("replays", data)
        self.assertIsInstance(data["replays"], list)

    # ---- WO 3.1 model forwarding ----------------------------------------
    def test_model_in_post_body_forwarded_to_bridge_run(self):
        """When the POST body contains model=haiku, bridge.run is called with model='haiku'."""
        received = {}
        orig_run = server.bridge.run

        def _capture_run(*args, **kwargs):
            received.update(kwargs)
            return orig_run(*args, **kwargs)

        server.bridge.run = _capture_run
        try:
            with _ServerHarness() as h:
                h.post_run({"query": "Is TSC2 viable?", "profile": "demo", "model": "haiku"})
        finally:
            server.bridge.run = orig_run

        self.assertEqual(received.get("model"), "haiku",
                         "model='haiku' in POST body must reach bridge.run(model=...)")

    def test_empty_model_in_post_body_no_model_override(self):
        """When model is absent or empty in POST body, bridge.run is called with model=None."""
        received = {}
        orig_run = server.bridge.run

        def _capture_run(*args, **kwargs):
            received.update(kwargs)
            return orig_run(*args, **kwargs)

        server.bridge.run = _capture_run
        try:
            with _ServerHarness() as h:
                # No model field at all
                h.post_run({"query": "Is TSC2 viable?", "profile": "demo"})
        finally:
            server.bridge.run = orig_run

        # model=None or model not present both mean "no override"
        self.assertIsNone(received.get("model"),
                          "absent model in POST body must result in model=None to bridge.run")

    def test_replay_profile_ignores_model(self):
        """replay profile calls bridge.replay (not bridge.run), so model is silently ignored."""
        bridge_run_calls = []
        bridge_replay_calls = []
        orig_run = server.bridge.run
        orig_replay = server.bridge.replay

        def _track_run(*args, **kwargs):
            bridge_run_calls.append(kwargs)
            return orig_run(*args, **kwargs)

        def _track_replay(*args, **kwargs):
            bridge_replay_calls.append(args)
            return orig_replay(*args, **kwargs)

        server.bridge.run = _track_run
        server.bridge.replay = _track_replay
        try:
            with _ServerHarness() as h:
                h.post_run({"query": "", "profile": "replay", "model": "haiku"})
        finally:
            server.bridge.run = orig_run
            server.bridge.replay = orig_replay

        # For replay, bridge.replay was called (not bridge.run), so model was NOT forwarded.
        self.assertTrue(bridge_replay_calls, "bridge.replay must be called for profile=replay")
        self.assertFalse(bridge_run_calls, "bridge.run must NOT be called for profile=replay")

    # ---- URL-param preselection (B-6) ------------------------------------
    def test_app_js_served_and_contains_url_param_preselection(self):
        """app.js must be served at /static/app.js and must contain the
        URLSearchParams preselection logic so that ?mode=replay (shareable link)
        preselects the `replay` profile in the dropdown on load."""
        with _ServerHarness() as h:
            status, body, headers = h.get("/static/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers.get("Content-Type", "").lower())
        # The feature: URLSearchParams read on page load — anchored to the IIFE's unique logic.
        self.assertIn("URLSearchParams", body,
                      "app.js must read URLSearchParams for ?mode=replay preselection")
        # The mode=replay → "replay" mapping is the key contract: a link with ?mode=replay
        # must select the $0 canned-replay profile.  This literal only appears in the IIFE.
        self.assertIn('params.get("mode") === "replay"', body,
                      'IIFE must map mode=replay to the replay profile')
        # profileSel.value is set inside the IIFE (unique to the new code).
        self.assertIn("profileSel.value = target", body,
                      "IIFE must preselect the dropdown by setting profileSel.value")


class TestFullAccess(unittest.TestCase):
    """The Demo-Claude full-backend-access surface: the COMPLETE result over SSE,
    GET /api/trace/<id> (raw JSONL), GET /api/runs/<id> (cached full dict).

    Engagement traces are isolated to a temp dir (SAPPHIRE_ENGAGEMENTS_DIR) so the
    server's /api/trace resolution and the harness writer agree, and real state is untouched.
    """
    def setUp(self):
        self._eng = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._eng
        os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)

    def _run_and_get_result(self, h):
        raw = h.post_run({"query": "Is TSC2 a viable target in tuberous sclerosis?",
                          "profile": "demo"})
        events = _parse_sse(raw)
        results = [d for e, d in events if e == "result"]
        self.assertEqual(len(results), 1)
        return results[0]

    def test_result_carries_the_complete_run_live_dict(self):
        """The hard requirement: the `result` frame is the COMPLETE run_live dict — every
        documented top-level key + full dossier/flags/spread/synthesis, no truncation."""
        with _ServerHarness() as h:
            result = self._run_and_get_result(h)
        for key in ("query", "plan", "priors", "discover", "consult",
                    "synthesize", "engagement_id", "reflection", "_via"):
            self.assertIn(key, result, f"result missing top-level key {key!r}")
        # every dossier fact carries the full field set (no summarisation)
        dossier = result["discover"]["dossier"]
        self.assertTrue(dossier)
        for f in dossier:
            for fld in ("value", "tier", "provenance", "plane"):
                self.assertIn(fld, f)
        # flags present (all three buckets), the full spread, the synthesis
        for fl in ("VETO", "DIVERGENCE", "KNOWN_UNKNOWNS"):
            self.assertIn(fl, result["discover"]["flags"])
        self.assertTrue(result["consult"]["round1"])
        for v in result["consult"]["round1"]:
            self.assertIn("persona", v); self.assertIn("stance", v); self.assertIn("status", v)
        self.assertTrue(result["engagement_id"])

    def test_trace_endpoint_returns_raw_jsonl(self):
        """GET /api/trace/<id> returns the raw append-only trace JSONL for that engagement."""
        with _ServerHarness() as h:
            result = self._run_and_get_result(h)
            eid = result["engagement_id"]
            status, body, headers = h.get("/api/trace/" + eid)
        self.assertEqual(status, 200)
        self.assertIn("ndjson", headers.get("Content-Type", ""))
        lines = [l for l in body.splitlines() if l.strip()]
        self.assertTrue(lines, "trace JSONL must have at least one event line")
        # each line is a JSON object carrying the engagement id + a timestamp
        first = json.loads(lines[0])
        self.assertEqual(first.get("engagement_id"), eid)
        self.assertIn("ts", first)
        # the trace records real harness events (statuses) — the audit surface
        kinds = {json.loads(l).get("type") for l in lines}
        self.assertTrue(kinds, "trace events should carry a type")

    def test_trace_404_for_unknown_engagement(self):
        with _ServerHarness() as h:
            try:
                h.get("/api/trace/eng_does_not_exist")
                self.fail("unknown engagement trace should 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)

    def test_trace_path_traversal_blocked(self):
        with _ServerHarness() as h:
            try:
                h.get("/api/trace/..%2f..%2fetc")  # invalid id chars
                self.fail("path traversal id should be rejected")
            except urllib.error.HTTPError as e:
                self.assertIn(e.code, (400, 403, 404))

    def test_runs_endpoint_returns_cached_full_dict(self):
        """GET /api/runs/<id> returns the COMPLETE cached result dict from the last run."""
        with _ServerHarness() as h:
            result = self._run_and_get_result(h)
            eid = result["engagement_id"]
            status, body, headers = h.get("/api/runs/" + eid)
        self.assertEqual(status, 200)
        self.assertIn("json", headers.get("Content-Type", ""))
        cached = json.loads(body)
        # identical complete dict (same engagement, same dossier size, same synthesis)
        self.assertEqual(cached["engagement_id"], eid)
        self.assertEqual(len(cached["discover"]["dossier"]), len(result["discover"]["dossier"]))
        self.assertEqual(cached["synthesize"]["recommendation"], result["synthesize"]["recommendation"])

    def test_runs_404_for_unknown_engagement(self):
        with _ServerHarness() as h:
            try:
                h.get("/api/runs/eng_never_ran")
                self.fail("uncached engagement should 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)


class TestSSEEncoding(unittest.TestCase):
    """Unit-level checks on the pure SSE encoder + profile mapping (no socket)."""

    def test_sse_frame_format(self):
        frame = server._sse("progress", {"stage": "plan", "phase": "done"}).decode("utf-8")
        self.assertTrue(frame.startswith("event: progress\n"))
        self.assertIn("data: ", frame)
        self.assertTrue(frame.endswith("\n\n"))   # blank-line terminated
        # the data line round-trips
        data_line = [l for l in frame.split("\n") if l.startswith("data:")][0]
        obj = json.loads(data_line[len("data:"):].strip())
        self.assertEqual(obj["stage"], "plan")

    def test_profile_kwargs_mapping(self):
        self.assertEqual(server._profile_kwargs("demo"), {"mock": True})
        self.assertEqual(server._profile_kwargs("live"), {"mock": False})
        self.assertEqual(server._profile_kwargs("simulate"), {"mock": False, "simulate": True})
        # unknown profile → safe offline default
        self.assertEqual(server._profile_kwargs("???"), {"mock": True})


class TestStepChat(unittest.TestCase):
    """POST /api/step-chat — the scoped side-chat endpoint (WO-8 Phase 3).

    `scoped_chat.answer_scoped` is mocked here (it shells out to `claude`); the
    point of these tests is the HTTP plumbing — request parsing, response shape,
    and that the handler forwards exactly the `facts` list it was given (never
    widens scope), not re-testing answer_scoped's own honesty guard (that's
    sapphire-orchestrator/tests/test_scoped_chat.py's job)."""

    def test_step_chat_returns_answer_json(self):
        import scoped_chat
        from unittest.mock import patch

        with patch.object(scoped_chat, "answer_scoped", return_value="TSC2 suppresses mTORC1.") as mock_answer:
            with _ServerHarness() as h:
                status, body, _ = h.post_json("/api/step-chat", {
                    "question": "What does TSC2 do?",
                    "facts": [{"value": "TSC2 suppresses mTORC1", "source": "PMID:12345",
                               "tier": "T2", "provenance": "emet-live"}],
                    "agent_id": "emet-runner",
                })
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["answer"], "TSC2 suppresses mTORC1.")
        mock_answer.assert_called_once()

    def test_step_chat_forwards_only_the_given_facts_never_widens_scope(self):
        """The handler must pass through EXACTLY the `facts` array the client
        sent — proving the server-side seam doesn't substitute the whole
        dossier or any other facts behind the client's back."""
        import scoped_chat
        from unittest.mock import patch

        scoped_facts = [
            {"value": "TSC2 suppresses mTORC1", "source": "PMID:12345",
             "tier": "T2", "provenance": "emet-live"},
        ]
        with patch.object(scoped_chat, "answer_scoped", return_value="ok") as mock_answer:
            with _ServerHarness() as h:
                h.post_json("/api/step-chat", {
                    "question": "explain",
                    "facts": scoped_facts,
                    "agent_id": "emet-runner",
                })
        called_question, called_facts = mock_answer.call_args[0][:2]
        self.assertEqual(called_question, "explain")
        self.assertEqual(called_facts, scoped_facts)

    def test_step_chat_missing_facts_degrades_to_empty_list(self):
        """A malformed/absent `facts` key must not crash the handler — it
        degrades to an empty list (honest: no evidence), never a 500."""
        import scoped_chat
        from unittest.mock import patch

        with patch.object(scoped_chat, "answer_scoped", return_value="No evidence available.") as mock_answer:
            with _ServerHarness() as h:
                status, body, _ = h.post_json("/api/step-chat", {"question": "explain"})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["answer"], "No evidence available.")
        called_facts = mock_answer.call_args[0][1]
        self.assertEqual(called_facts, [])

    def test_step_chat_unknown_path_is_404(self):
        with _ServerHarness() as h:
            try:
                h.post_json("/api/step-chat-typo", {"question": "x"})
                self.fail("unknown path should 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)


if __name__ == "__main__":
    unittest.main()
