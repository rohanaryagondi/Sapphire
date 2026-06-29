"""Tests for the Wave-1 persistence API endpoints in frontend2/server.py.

Exercises the real Handler over a real socket (ephemeral port) with an isolated
temp-dir SQLite db so no real state is touched.

Routes tested:
  GET  /api/conversations          → list
  GET  /api/conversations/<id>     → detail or 404
  POST /api/conversations          → create
  PATCH /api/conversations/<id>    → rename or star
  DELETE /api/conversations/<id>   → delete or 404
  POST /api/run (extended)         → stores to db, injects _conversation_id into result
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


# --------------------------------------------------------------------------- #
# Shared helpers (adapted from test_server.py)                                #
# --------------------------------------------------------------------------- #

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

    def get(self, path: str, timeout: float = 10.0):
        with urllib.request.urlopen(self.base + path, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8"), resp.headers

    def post_run(self, body: dict, timeout: float = 60.0) -> str:
        """POST /api/run → full SSE text."""
        req = urllib.request.Request(
            self.base + "/api/run",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")

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

    def patch(self, path: str, body: dict, timeout: float = 10.0):
        """PATCH a JSON body and return (status, body_text, headers)."""
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8"), resp.headers

    def delete(self, path: str, timeout: float = 10.0):
        """DELETE and return (status, body_text, headers)."""
        req = urllib.request.Request(
            self.base + path,
            method="DELETE",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8"), resp.headers


# --------------------------------------------------------------------------- #
# Tests                                                                        #
# --------------------------------------------------------------------------- #

class TestStoreAPI(unittest.TestCase):
    """API-level tests for Wave-1 persistence routes. Each test gets a fresh temp db."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self._engagements_dir = tempfile.mkdtemp()
        self._memory_dir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_STORE_DB"] = str(Path(self._tmpdir) / "sapphire_test.db")
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self._engagements_dir
        os.environ["SAPPHIRE_MEMORY_DIR"] = self._memory_dir
        # Reload store module so it picks up the new SAPPHIRE_STORE_DB.
        import store
        importlib.reload(store)

    def tearDown(self):
        os.environ.pop("SAPPHIRE_STORE_DB", None)
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)
        os.environ.pop("SAPPHIRE_MEMORY_DIR", None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        shutil.rmtree(self._engagements_dir, ignore_errors=True)
        shutil.rmtree(self._memory_dir, ignore_errors=True)

    # ---------------------------------------------------------------------- #
    # POST /api/conversations                                                  #
    # ---------------------------------------------------------------------- #

    def test_post_conversations_creates(self):
        """POST /api/conversations → 200 with id string."""
        with _ServerHarness() as h:
            status, body, _ = h.post_json("/api/conversations", {"title": "My test chat"})
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("id", data, "response must have an 'id' key")
        self.assertIsInstance(data["id"], str)
        self.assertTrue(data["id"], "id must be non-empty")

    def test_post_conversations_default_title(self):
        """POST /api/conversations without title uses 'New conversation'."""
        with _ServerHarness() as h:
            _, body, _ = h.post_json("/api/conversations", {})
        data = json.loads(body)
        self.assertIn("id", data)
        import store
        conv = store.get_conversation(data["id"])
        self.assertIsNotNone(conv)
        self.assertEqual(conv["conversation"]["title"], "New conversation")

    # ---------------------------------------------------------------------- #
    # GET /api/conversations                                                   #
    # ---------------------------------------------------------------------- #

    def test_get_conversations_list(self):
        """Create 2 conversations via POST; GET list returns exactly 2."""
        with _ServerHarness() as h:
            h.post_json("/api/conversations", {"title": "First"})
            h.post_json("/api/conversations", {"title": "Second"})
            status, body, _ = h.get("/api/conversations")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("conversations", data)
        self.assertEqual(len(data["conversations"]), 2)

    def test_get_conversations_empty_list(self):
        """GET /api/conversations when no conversations → {conversations: []}."""
        with _ServerHarness() as h:
            status, body, _ = h.get("/api/conversations")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["conversations"], [])

    # ---------------------------------------------------------------------- #
    # GET /api/conversations/<id>                                              #
    # ---------------------------------------------------------------------- #

    def test_get_conversation_detail(self):
        """Create via POST, add a message via store, GET detail has messages + runs keys."""
        import store as _store
        with _ServerHarness() as h:
            _, body, _ = h.post_json("/api/conversations", {"title": "Detail test"})
            cid = json.loads(body)["id"]
            # Add a message directly via store (the server exposes conversations/messages
            # together — this is intentional: the detail view aggregates them).
            _store.add_message(cid, "user", "Hello from test")
            status, detail_body, _ = h.get(f"/api/conversations/{cid}")
        self.assertEqual(status, 200)
        data = json.loads(detail_body)
        self.assertIn("conversation", data)
        self.assertIn("messages", data)
        self.assertIn("runs", data)
        self.assertEqual(len(data["messages"]), 1)
        self.assertEqual(data["messages"][0]["content"], "Hello from test")

    def test_get_nonexistent(self):
        """GET /api/conversations/does-not-exist → 404."""
        with _ServerHarness() as h:
            try:
                h.get("/api/conversations/does-not-exist")
                self.fail("should have raised HTTPError 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)

    # ---------------------------------------------------------------------- #
    # PATCH /api/conversations/<id>                                            #
    # ---------------------------------------------------------------------- #

    def test_patch_rename(self):
        """PATCH {title} updates the conversation title visible in GET detail."""
        with _ServerHarness() as h:
            _, body, _ = h.post_json("/api/conversations", {"title": "Original"})
            cid = json.loads(body)["id"]
            patch_status, patch_body, _ = h.patch(
                f"/api/conversations/{cid}", {"title": "renamed"}
            )
            self.assertEqual(patch_status, 200)
            self.assertTrue(json.loads(patch_body)["ok"])
            _, detail_body, _ = h.get(f"/api/conversations/{cid}")
        data = json.loads(detail_body)
        self.assertEqual(data["conversation"]["title"], "renamed")

    def test_patch_star(self):
        """PATCH {starred: true} makes starred=true in the list."""
        with _ServerHarness() as h:
            _, body, _ = h.post_json("/api/conversations", {"title": "Star test"})
            cid = json.loads(body)["id"]
            h.patch(f"/api/conversations/{cid}", {"starred": True})
            _, list_body, _ = h.get("/api/conversations")
        data = json.loads(list_body)
        matching = [c for c in data["conversations"] if c["id"] == cid]
        self.assertEqual(len(matching), 1)
        self.assertTrue(matching[0]["starred"], "conversation must be starred")

    # ---------------------------------------------------------------------- #
    # DELETE /api/conversations/<id>                                           #
    # ---------------------------------------------------------------------- #

    def test_delete(self):
        """DELETE a conversation; it disappears from the list."""
        with _ServerHarness() as h:
            _, body, _ = h.post_json("/api/conversations", {"title": "To delete"})
            cid = json.loads(body)["id"]
            del_status, del_body, _ = h.delete(f"/api/conversations/{cid}")
            self.assertEqual(del_status, 200)
            self.assertTrue(json.loads(del_body)["ok"])
            _, list_body, _ = h.get("/api/conversations")
        data = json.loads(list_body)
        ids = [c["id"] for c in data["conversations"]]
        self.assertNotIn(cid, ids)

    def test_delete_nonexistent(self):
        """DELETE /api/conversations/nonexistent → 404."""
        with _ServerHarness() as h:
            try:
                h.delete("/api/conversations/no-such-id")
                self.fail("should have raised HTTPError 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)

    def test_patch_nonexistent_returns_404(self):
        """PATCH /api/conversations/nonexistent → 404, not a silent 200."""
        with _ServerHarness() as h:
            try:
                h.patch("/api/conversations/no-such-id", {"title": "ghost"})
                self.fail("PATCH on missing conv must raise HTTPError 404")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 404)

    # ---------------------------------------------------------------------- #
    # POST /api/run extended — store save + _conversation_id injection         #
    # ---------------------------------------------------------------------- #

    def test_run_saves_to_store(self):
        """POST /api/run (demo) → SSE result event carries _conversation_id.

        After the run, the conversation is in the store with at least one run.
        """
        with _ServerHarness() as h:
            raw = h.post_run({"query": "Is TSC2 viable?", "profile": "demo"})
        events = _parse_sse(raw)
        results = [d for e, d in events if e == "result"]
        self.assertEqual(len(results), 1, "must have exactly one result event")
        result = results[0]
        self.assertIn("_conversation_id", result,
                      "result must carry _conversation_id for the client to use")
        cid = result["_conversation_id"]
        # The conversation and run must be persisted.
        import store as _store
        conv = _store.get_conversation(cid)
        self.assertIsNotNone(conv, "conversation must be in the store")
        self.assertTrue(conv["runs"], "at least one run must be saved")
        self.assertIn("_run_id", result, "result must also carry _run_id")

    def test_run_with_existing_conversation(self):
        """POST /api/run with conversation_id → run attached to existing conv; no new conv created."""
        import store as _store
        cid = _store.create_conversation("Pre-existing")
        with _ServerHarness() as h:
            raw = h.post_run({
                "query": "Is TSC2 viable?",
                "profile": "demo",
                "conversation_id": cid,
            })
        events = _parse_sse(raw)
        kinds = [e for e, _ in events]
        # Must complete cleanly (result not error).
        self.assertNotIn("error", kinds,
                         "run with existing conversation_id must not produce an error frame")
        self.assertIn("result", kinds)
        # Still exactly one conversation (the pre-existing one).
        convs = _store.list_conversations()
        self.assertEqual(len(convs), 1)
        self.assertEqual(convs[0]["id"], cid)


if __name__ == "__main__":
    unittest.main()
