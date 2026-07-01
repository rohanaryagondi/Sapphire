"""Tests for POST /api/reinvoke in frontend2/server.py — WO-9 Phase 5.

Exercises the real Handler over a real socket (ephemeral port) with an isolated
temp-dir SQLite db so no real state is touched. Mirrors test_followup_api.py's
harness exactly. The actual agent/tool dispatch (`reinvoke.reinvoke_agent`) is
mocked — this test suite is about the SERVER's persistence + effective-evidence +
re-answer wiring, not the dispatch internals (covered by tests/test_reinvoke.py).
Run with CLAUDE_BIN=/usr/bin/false so followup.answer_followup's real subprocess
call resolves fast/deterministically (no CPU storm) rather than hitting a real
claude binary.
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
from unittest.mock import patch

_HERE = Path(__file__).resolve().parents[1]  # frontend2/
_REPO = _HERE.parent
for _p in (str(_HERE), str(_REPO / "frontend"), str(_REPO / "sapphire-orchestrator")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import server  # noqa: E402  (frontend2/server.py)
import reinvoke  # noqa: E402  (sapphire-orchestrator/reinvoke.py) — patched per-test


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


_OK_REINVOKE = {
    "ok": True,
    "new_facts": [{
        "value": "FAERS shows elevated AE reports for this class.",
        "source": "FAERS", "tier": "T2", "provenance": "semantic-web",
        "plane": "external", "agent_id": "post-market-safety",
    }],
    "agent_id": "post-market-safety",
    "engagement_id": "eng_reinvoke_test",
    "error": None,
}

_FAIL_REINVOKE = {
    "ok": False, "new_facts": [], "agent_id": "post-market-safety",
    "engagement_id": None, "error": "simulated dispatch failure",
}


class TestReinvokeAPI(unittest.TestCase):
    """API-level tests for POST /api/reinvoke. Each test gets a fresh temp db."""

    def setUp(self):
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
    # Validation                                                               #
    # ---------------------------------------------------------------------- #

    def test_missing_agent_id_400(self):
        import store as _store
        cid = _store.create_conversation("Test")
        with _ServerHarness() as h:
            status, body, _ = h.post_json(
                "/api/reinvoke", {"conversation_id": cid, "agent_id": "", "question": "Why?"}
            )
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(body))

    def test_missing_question_400(self):
        import store as _store
        cid = _store.create_conversation("Test")
        with _ServerHarness() as h:
            status, body, _ = h.post_json(
                "/api/reinvoke", {"conversation_id": cid, "agent_id": "post-market-safety", "question": ""}
            )
        self.assertEqual(status, 400)

    def test_nonexistent_conversation_404(self):
        with _ServerHarness() as h:
            status, body, _ = h.post_json(
                "/api/reinvoke",
                {"conversation_id": "no-such-conv", "agent_id": "post-market-safety", "question": "Why?"},
            )
        self.assertEqual(status, 404)

    def test_no_run_yet_returns_honest_400(self):
        import store as _store
        cid = _store.create_conversation("Empty conv")
        with _ServerHarness() as h:
            status, body, _ = h.post_json(
                "/api/reinvoke",
                {"conversation_id": cid, "agent_id": "post-market-safety", "question": "Anything?"},
            )
        self.assertEqual(status, 400)
        data = json.loads(body)
        self.assertIn("no run yet", data["error"])

    # ---------------------------------------------------------------------- #
    # Happy path                                                               #
    # ---------------------------------------------------------------------- #

    def test_reinvoke_persists_row_and_returns_updated_answer(self):
        with patch.object(reinvoke, "reinvoke_agent", return_value=_OK_REINVOKE):
            with _ServerHarness() as h:
                raw = h.post_run({"query": "Is TSC2 viable?", "profile": "demo"})
                result = [d for e, d in _parse_sse(raw) if e == "result"][0]
                cid = result["_conversation_id"]
                real_run_id = result["_run_id"]

                status, body, _ = h.post_json("/api/reinvoke", {
                    "conversation_id": cid,
                    "agent_id": "post-market-safety",
                    "question": "What does FAERS show for this class?",
                })
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["ok"])
        for key in ("answer", "citations", "needs_new_data", "missing_agent",
                    "missing_agent_label", "new_facts", "agent_id", "source_run_id"):
            self.assertIn(key, data)
        self.assertEqual(data["agent_id"], "post-market-safety")
        self.assertEqual(data["source_run_id"], real_run_id)
        self.assertEqual(len(data["new_facts"]), 1)

        # Persisted: a via="reinvoke" row now exists, chained to the real run.
        import store as _store
        conv = _store.get_conversation(cid)
        vias = [r["via"] for r in conv["runs"]]
        self.assertIn("reinvoke", vias)

        # The stored ORIGINAL run must be untouched (append-only design).
        original = _store.get_run(real_run_id)["result_json"]
        original_n_facts = len(original["discover"]["dossier"])

        # But the EFFECTIVE evidence now includes the new fact.
        ev = _store.get_effective_evidence(cid)
        self.assertEqual(len(ev["result"]["discover"]["dossier"]), original_n_facts + 1)

    def test_reinvoke_failure_returns_honest_ok_false_never_fabricates(self):
        with patch.object(reinvoke, "reinvoke_agent", return_value=_FAIL_REINVOKE):
            with _ServerHarness() as h:
                raw = h.post_run({"query": "Is TSC2 viable?", "profile": "demo"})
                result = [d for e, d in _parse_sse(raw) if e == "result"][0]
                cid = result["_conversation_id"]

                status, body, _ = h.post_json("/api/reinvoke", {
                    "conversation_id": cid,
                    "agent_id": "post-market-safety",
                    "question": "What does FAERS show?",
                })
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertFalse(data["ok"])
        self.assertIn("simulated dispatch failure", data["error"])
        self.assertNotIn("answer", data, "a failed re-invocation must never fabricate an answer")

        # No via="reinvoke" row must be persisted on failure.
        import store as _store
        conv = _store.get_conversation(cid)
        vias = [r["via"] for r in conv["runs"]]
        self.assertNotIn("reinvoke", vias)

    def test_followup_after_reinvoke_sees_the_grown_evidence(self):
        """A follow-up asked AFTER a re-invocation must answer from the GROWN dossier
        (the shared get_effective_evidence helper), not just the original facts."""
        with patch.object(reinvoke, "reinvoke_agent", return_value=_OK_REINVOKE):
            with _ServerHarness() as h:
                raw = h.post_run({"query": "Is TSC2 viable?", "profile": "demo"})
                result = [d for e, d in _parse_sse(raw) if e == "result"][0]
                cid = result["_conversation_id"]

                h.post_json("/api/reinvoke", {
                    "conversation_id": cid, "agent_id": "post-market-safety",
                    "question": "FAERS signal?",
                })

                status, body, _ = h.post_json(
                    "/api/followup", {"conversation_id": cid, "question": "Summarize everything."}
                )
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["answer"].strip())
        # The followup's source_run_id must still be the ORIGINAL real run (reinvoke
        # rows are evidence-only, never themselves an evidence source).
        import store as _store
        conv = _store.get_conversation(cid)
        real_run = next(r for r in conv["runs"] if r["via"] not in ("followup", "reinvoke"))
        self.assertEqual(data["source_run_id"], real_run["id"])

    def test_invalid_agent_id_degrades_honestly(self):
        """No mock — exercises the REAL reinvoke.reinvoke_agent unknown-id path
        end-to-end through the server."""
        with _ServerHarness() as h:
            raw = h.post_run({"query": "Is TSC2 viable?", "profile": "demo"})
            result = [d for e, d in _parse_sse(raw) if e == "result"][0]
            cid = result["_conversation_id"]

            status, body, _ = h.post_json("/api/reinvoke", {
                "conversation_id": cid,
                "agent_id": "not-a-real-agent-or-tool",
                "question": "Anything?",
            })
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertFalse(data["ok"])
        self.assertIsNotNone(data["error"])


if __name__ == "__main__":
    unittest.main()
