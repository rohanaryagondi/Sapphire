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
        with _ServerHarness() as h:
            raw = h.post_run({"query": "Is TSC2 a viable target in tuberous sclerosis?",
                              "profile": "demo"})
        events = _parse_sse(raw)
        results = [d for e, d in events if e == "result"]
        self.assertEqual(len(results), 1)
        result = results[0]
        # The streamed result conforms to the documented run_live contract (additive keys ok).
        self.assertEqual(validate_run_live(result), [])
        # Real dossier content lands: two planes, a roundtable spread, a synthesis.
        dossier = result["discover"]["dossier"]
        self.assertTrue(dossier)
        planes = {f.get("plane") for f in dossier}
        self.assertIn("internal", planes)
        self.assertIn("external", planes)
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


if __name__ == "__main__":
    unittest.main()
