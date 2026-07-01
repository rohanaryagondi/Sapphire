"""Tests for POST /api/followup in frontend2/server.py — WO-9 Phase 1.

Exercises the real Handler over a real socket (ephemeral port) with an isolated
temp-dir SQLite db so no real state is touched. Mirrors test_store_api.py's
harness. Run with CLAUDE_BIN=/usr/bin/false so followup.answer_followup's real
subprocess call resolves fast/deterministically (no CPU storm) rather than
hitting a real claude binary.
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]  # frontend2/
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

    def get(self, path: str, timeout: float = 10.0):
        with urllib.request.urlopen(self.base + path, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8"), resp.headers

    def post_run(self, body: dict, timeout: float = 60.0) -> str:
        req = urllib.request.Request(
            self.base + "/api/run",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")

    def post_json(self, path: str, body: dict, timeout: float = 30.0):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8"), resp.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8"), e.headers


class TestFollowupAPI(unittest.TestCase):
    """API-level tests for POST /api/followup. Each test gets a fresh temp db."""

    def setUp(self):
        # Hermetic: force the fast no-op binary so followup.py's real subprocess
        # call resolves instantly instead of spawning a real `claude` process.
        self._orig_claude_bin = os.environ.get("CLAUDE_BIN")
        os.environ["CLAUDE_BIN"] = "/usr/bin/false"
        self._tmpdir = tempfile.mkdtemp()
        self._engagements_dir = tempfile.mkdtemp()
        self._memory_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_STORE_DB"] = str(Path(self._tmpdir) / "sapphire_test.db")
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._engagements_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._memory_dir
        import store
        importlib.reload(store)

    def tearDown(self):
        os.environ.pop("SAPPHIRE_STORE_DB", None)
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)
        if self._orig_claude_bin is None:
            os.environ.pop("CLAUDE_BIN", None)
        else:
            os.environ["CLAUDE_BIN"] = self._orig_claude_bin
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        shutil.rmtree(self._engagements_dir, ignore_errors=True)
        shutil.rmtree(self._memory_dir, ignore_errors=True)

    # ---------------------------------------------------------------------- #
    # Validation                                                                #
    # ---------------------------------------------------------------------- #

    def test_missing_question_400(self):
        import store as _store
        cid = _store.create_conversation("Test")
        with _ServerHarness() as h:
            status, body, _ = h.post_json("/api/followup", {"conversation_id": cid, "question": ""})
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(body))

    def test_missing_conversation_id_400(self):
        with _ServerHarness() as h:
            status, body, _ = h.post_json("/api/followup", {"conversation_id": "", "question": "Why?"})
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(body))

    def test_nonexistent_conversation_404(self):
        with _ServerHarness() as h:
            status, body, _ = h.post_json(
                "/api/followup", {"conversation_id": "no-such-conv", "question": "Why?"}
            )
        self.assertEqual(status, 404)

    def test_no_run_yet_returns_honest_400(self):
        """A conversation with zero real runs must not fabricate an answer."""
        import store as _store
        cid = _store.create_conversation("Empty conv")
        with _ServerHarness() as h:
            status, body, _ = h.post_json(
                "/api/followup", {"conversation_id": cid, "question": "Anything?"}
            )
        self.assertEqual(status, 400)
        data = json.loads(body)
        self.assertIn("no run yet", data["error"])

    # ---------------------------------------------------------------------- #
    # Happy path                                                               #
    # ---------------------------------------------------------------------- #

    def test_followup_answers_from_stored_run(self):
        """POST /api/run (demo) creates a real run; POST /api/followup then answers
        from that run's stored evidence and persists both as a followup run."""
        with _ServerHarness() as h:
            raw = h.post_run({"query": "Is TSC2 viable?", "profile": "demo"})
            result = [d for e, d in _parse_sse(raw) if e == "result"][0]
            cid = result["_conversation_id"]

            status, body, _ = h.post_json(
                "/api/followup", {"conversation_id": cid, "question": "What did the dossier say?"}
            )
        self.assertEqual(status, 200)
        data = json.loads(body)
        for key in ("answer", "citations", "needs_new_data", "missing_agent", "source_run_id", "conversation_id"):
            self.assertIn(key, data)
        self.assertTrue(data["answer"].strip())
        self.assertEqual(data["conversation_id"], cid)
        self.assertTrue(data["source_run_id"])

        # Persisted: the conversation now has 2 runs (the original + the followup).
        import store as _store
        conv = _store.get_conversation(cid)
        vias = [r["via"] for r in conv["runs"]]
        self.assertIn("followup", vias)
        self.assertEqual(vias.count("followup"), 1)

    def test_second_followup_still_answers_from_original_run_not_followup(self):
        """A follow-up on top of a follow-up must still pick the last REAL firm run,
        never a prior followup run, as the evidence source."""
        with _ServerHarness() as h:
            raw = h.post_run({"query": "Is TSC2 viable?", "profile": "demo"})
            result = [d for e, d in _parse_sse(raw) if e == "result"][0]
            cid = result["_conversation_id"]
            real_run_id = result["_run_id"]

            h.post_json("/api/followup", {"conversation_id": cid, "question": "First follow-up?"})
            status, body, _ = h.post_json(
                "/api/followup", {"conversation_id": cid, "question": "Second follow-up?"}
            )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["source_run_id"], real_run_id,
                         "must always answer from the original real run, not a prior followup")

    def test_followup_persists_user_and_assistant_messages(self):
        with _ServerHarness() as h:
            raw = h.post_run({"query": "Is TSC2 viable?", "profile": "demo"})
            result = [d for e, d in _parse_sse(raw) if e == "result"][0]
            cid = result["_conversation_id"]
            h.post_json("/api/followup", {"conversation_id": cid, "question": "Explain more"})

        import store as _store
        conv = _store.get_conversation(cid)
        roles = [m["role"] for m in conv["messages"]]
        self.assertIn("user", roles)
        self.assertIn("assistant", roles)


if __name__ == "__main__":
    unittest.main()
