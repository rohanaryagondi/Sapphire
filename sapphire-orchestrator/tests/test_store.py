"""Tests for sapphire-orchestrator/store.py — SQLite conversation + run history.

Each test method gets a fresh temporary db (setUp creates it, tearDown deletes it),
so tests are fully isolated and never touch real state.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

# Add sapphire-orchestrator/ to sys.path so `import store` works when this
# file is run directly (e.g. python -m unittest tests/test_store.py -v).
_ORCH = Path(__file__).resolve().parents[1]  # sapphire-orchestrator/
if str(_ORCH) not in sys.path:
    sys.path.insert(0, str(_ORCH))

import store  # noqa: E402


class TestStore(unittest.TestCase):
    """Isolated per-test db via SAPPHIRE_STORE_DB env override."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        os.environ["SAPPHIRE_STORE_DB"] = str(Path(self._tmpdir) / "sapphire_test.db")

    def tearDown(self):
        os.environ.pop("SAPPHIRE_STORE_DB", None)
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    # ---------------------------------------------------------------------- #
    # create + list                                                            #
    # ---------------------------------------------------------------------- #

    def test_create_and_list(self):
        """Create 2 conversations; list returns both, newest updated_at first."""
        c1 = store.create_conversation("Alpha")
        time.sleep(0.01)  # ensure distinct updated_at timestamps
        c2 = store.create_conversation("Beta")
        convs = store.list_conversations()
        self.assertEqual(len(convs), 2)
        # Newest-updated first (c2 was created last, so it has the later updated_at).
        self.assertEqual(convs[0]["id"], c2)
        self.assertEqual(convs[1]["id"], c1)
        # Field assertions on the first entry (c2).
        self.assertEqual(convs[0]["title"], "Beta")
        self.assertFalse(convs[0]["starred"])
        self.assertEqual(convs[0]["preview"], "")
        # Field assertions on c1.
        self.assertEqual(convs[1]["title"], "Alpha")

    # ---------------------------------------------------------------------- #
    # get_conversation                                                         #
    # ---------------------------------------------------------------------- #

    def test_get_conversation_not_found(self):
        result = store.get_conversation("nonexistent-id")
        self.assertIsNone(result)

    # ---------------------------------------------------------------------- #
    # add_message + preview                                                    #
    # ---------------------------------------------------------------------- #

    def test_add_message_and_preview(self):
        """After adding a user message, list_conversations preview shows its content."""
        cid = store.create_conversation("Test")
        store.add_message(cid, "user", "Is TSC2 viable?")
        convs = store.list_conversations()
        self.assertEqual(len(convs), 1)
        self.assertEqual(convs[0]["preview"], "Is TSC2 viable?")

    def test_add_message_preview_truncated_at_120(self):
        """A very long user message is truncated to 120 chars in the preview."""
        cid = store.create_conversation("Long")
        long_content = "x" * 200
        store.add_message(cid, "user", long_content)
        convs = store.list_conversations()
        self.assertEqual(len(convs[0]["preview"]), 120)

    def test_add_message_invalid_role(self):
        """add_message with an invalid role raises ValueError."""
        cid = store.create_conversation("Role test")
        with self.assertRaises(ValueError):
            store.add_message(cid, "robot", "hi")

    def test_add_message_valid_roles(self):
        """user, assistant, system are all valid roles."""
        cid = store.create_conversation("Roles")
        store.add_message(cid, "user", "hello")
        store.add_message(cid, "assistant", "hi back")
        store.add_message(cid, "system", "context")
        data = store.get_conversation(cid)
        self.assertEqual(len(data["messages"]), 3)

    # ---------------------------------------------------------------------- #
    # save_run + get_run                                                       #
    # ---------------------------------------------------------------------- #

    def test_save_run_round_trip(self):
        """save_run then get_run returns the original dict under result_json as a parsed dict."""
        cid = store.create_conversation("Run test")
        payload = {"query": "x", "score": 1}
        rid = store.save_run(cid, None, "x", payload, "test-via")
        run = store.get_run(rid)
        self.assertIsNotNone(run)
        self.assertEqual(run["id"], rid)
        self.assertEqual(run["conversation_id"], cid)
        self.assertIsNone(run["message_id"])
        self.assertEqual(run["query"], "x")
        self.assertIsInstance(run["result_json"], dict)
        self.assertEqual(run["result_json"]["score"], 1)
        self.assertEqual(run["via"], "test-via")

    def test_get_run_not_found(self):
        result = store.get_run("no-such-run")
        self.assertIsNone(result)

    # ---------------------------------------------------------------------- #
    # get_conversation includes messages + runs                                #
    # ---------------------------------------------------------------------- #

    def test_get_conversation_includes_messages_and_runs(self):
        """get_conversation returns messages list length 2 and runs list length 1.

        runs list must NOT include result_json (it's big; callers fetch by id if needed).
        """
        cid = store.create_conversation("Full")
        store.add_message(cid, "user", "Q1")
        store.add_message(cid, "assistant", "A1")
        rid = store.save_run(cid, None, "Q1", {"score": 99}, "eng-demo")
        data = store.get_conversation(cid)
        self.assertIsNotNone(data)
        self.assertEqual(len(data["messages"]), 2)
        self.assertEqual(len(data["runs"]), 1)
        # result_json must NOT be in the runs list entries (it's large).
        run_entry = data["runs"][0]
        self.assertNotIn("result_json", run_entry,
                         "runs list must not include result_json")
        self.assertEqual(run_entry["id"], rid)

    # ---------------------------------------------------------------------- #
    # rename                                                                   #
    # ---------------------------------------------------------------------- #

    def test_rename(self):
        """rename_conversation updates the title visible in list_conversations."""
        cid = store.create_conversation("Old title")
        changed = store.rename_conversation(cid, "New title")
        self.assertTrue(changed)
        convs = store.list_conversations()
        self.assertEqual(convs[0]["title"], "New title")

    def test_nonexistent_rename(self):
        result = store.rename_conversation("bad-id", "anything")
        self.assertFalse(result)

    # ---------------------------------------------------------------------- #
    # set_starred                                                              #
    # ---------------------------------------------------------------------- #

    def test_set_starred(self):
        """set_starred(True) makes starred=True in list_conversations."""
        cid = store.create_conversation("Star me")
        changed = store.set_starred(cid, True)
        self.assertTrue(changed)
        convs = store.list_conversations()
        self.assertTrue(convs[0]["starred"])

    def test_set_starred_false(self):
        """set_starred(False) after True → starred is False again."""
        cid = store.create_conversation("Unstar")
        store.set_starred(cid, True)
        store.set_starred(cid, False)
        convs = store.list_conversations()
        self.assertFalse(convs[0]["starred"])

    # ---------------------------------------------------------------------- #
    # delete                                                                   #
    # ---------------------------------------------------------------------- #

    def test_delete_cascades(self):
        """delete_conversation removes conv, messages, and runs (verified by direct query)."""
        cid = store.create_conversation("Doomed")
        mid = store.add_message(cid, "user", "Hello")
        store.save_run(cid, mid, "Hello", {"x": 1}, "demo")

        result = store.delete_conversation(cid)
        self.assertTrue(result)
        self.assertIsNone(store.get_conversation(cid))

        # Verify cascaded deletes directly via sqlite3.
        db_path = os.environ["SAPPHIRE_STORE_DB"]
        conn = sqlite3.connect(db_path)
        try:
            msg_count = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE conversation_id = ?", (cid,)
            ).fetchone()[0]
            run_count = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE conversation_id = ?", (cid,)
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(msg_count, 0, "all messages must be deleted")
        self.assertEqual(run_count, 0, "all runs must be deleted")

    def test_nonexistent_delete(self):
        result = store.delete_conversation("bad-id")
        self.assertFalse(result)

    # ---------------------------------------------------------------------- #
    # ordering                                                                 #
    # ---------------------------------------------------------------------- #

    def test_list_ordering(self):
        """list_conversations returns newest-updated_at first across 3 conversations."""
        c1 = store.create_conversation("First")
        time.sleep(0.01)
        c2 = store.create_conversation("Second")
        time.sleep(0.01)
        c3 = store.create_conversation("Third")
        convs = store.list_conversations()
        ids = [c["id"] for c in convs]
        self.assertEqual(ids[0], c3, "newest created (c3) must be first")
        self.assertEqual(ids[1], c2)
        self.assertEqual(ids[2], c1, "oldest created (c1) must be last")

    def test_add_message_bumps_updated_at_ordering(self):
        """Adding a message to an older conv bumps it to the top of the list."""
        c1 = store.create_conversation("Older")
        time.sleep(0.01)
        c2 = store.create_conversation("Newer")
        # Now add a message to c1 — its updated_at should now be later than c2's.
        time.sleep(0.01)
        store.add_message(c1, "user", "bump")
        convs = store.list_conversations()
        self.assertEqual(convs[0]["id"], c1,
                         "conv with most-recently-updated_at must be first")


if __name__ == "__main__":
    unittest.main()
