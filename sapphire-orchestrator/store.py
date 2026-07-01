"""store.py — SQLite persistence for Sapphire conversations + run history.

DB path = {REPO_ROOT}/RohanOnly/sapphire.sqlite by default.
Override with env var SAPPHIRE_STORE_DB (used by tests to point at a temp db).

Stdlib-only: sqlite3, json, uuid, pathlib, os.
No third-party imports. No module-level side effects beyond defining functions.
"""
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from pathlib import Path


# --------------------------------------------------------------------------- #
# Internal helpers                                                             #
# --------------------------------------------------------------------------- #

def _db_path() -> Path:
    """Resolve DB path from env or default. Read fresh each call so tests can override."""
    override = os.environ.get("SAPPHIRE_STORE_DB")
    if override:
        return Path(override)
    # store.py lives at sapphire-orchestrator/store.py
    # parents[0] = sapphire-orchestrator/   parents[1] = REPO root
    here = Path(__file__).resolve()
    repo = here.parent.parent
    return repo / "RohanOnly" / "sapphire.sqlite"


def _get_conn() -> sqlite3.Connection:
    """Open/create the DB, run _ensure_schema. New connection each call (thread-safe, WAL mode)."""
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables + indexes idempotently (CREATE … IF NOT EXISTS)."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            starred INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );

        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            message_id TEXT,
            query TEXT NOT NULL,
            result_json TEXT NOT NULL,
            via TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(conversation_id) REFERENCES conversations(id)
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
        CREATE INDEX IF NOT EXISTS idx_runs_conv ON runs(conversation_id);
    """)


def _now() -> str:
    """Current UTC time as ISO-8601 string.
    datetime is imported inside to avoid any top-level side effects."""
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    """Generate a new UUID string."""
    return str(uuid.uuid4())


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def create_conversation(title: str) -> str:
    """Insert a new conversation row; return its id."""
    cid = _new_id()
    now = _now()
    conn = _get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at, starred)"
                " VALUES (?, ?, ?, ?, 0)",
                (cid, title, now, now),
            )
    finally:
        conn.close()
    return cid


def list_conversations() -> list[dict]:
    """Return all conversations sorted by updated_at DESC, each with a preview.

    preview = first user message content (up to 120 chars) or "" if none.
    """
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT id, title, created_at, updated_at, starred"
            " FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
        result = []
        for row in rows:
            cid = row["id"]
            msg = conn.execute(
                "SELECT content FROM messages"
                " WHERE conversation_id = ? AND role = 'user'"
                " ORDER BY created_at ASC LIMIT 1",
                (cid,),
            ).fetchone()
            preview = msg["content"][:120] if msg else ""
            result.append({
                "id": cid,
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "starred": bool(row["starred"]),
                "preview": preview,
            })
        return result
    finally:
        conn.close()


def get_conversation(conv_id: str) -> "dict | None":
    """Return {conversation, messages, runs} or None if not found.

    runs list does NOT include result_json (callers fetch a single run by id if needed).
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, title, created_at, updated_at, starred"
            " FROM conversations WHERE id = ?",
            (conv_id,),
        ).fetchone()
        if row is None:
            return None
        messages = conn.execute(
            "SELECT id, role, content, created_at FROM messages"
            " WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,),
        ).fetchall()
        runs = conn.execute(
            "SELECT id, message_id, query, via, created_at FROM runs"
            " WHERE conversation_id = ? ORDER BY created_at ASC",
            (conv_id,),
        ).fetchall()
        return {
            "conversation": {
                "id": row["id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "starred": bool(row["starred"]),
            },
            "messages": [
                {
                    "id": m["id"],
                    "role": m["role"],
                    "content": m["content"],
                    "created_at": m["created_at"],
                }
                for m in messages
            ],
            "runs": [
                {
                    "id": r["id"],
                    "message_id": r["message_id"],
                    "query": r["query"],
                    "via": r["via"],
                    "created_at": r["created_at"],
                }
                for r in runs
            ],
        }
    finally:
        conn.close()


def get_run(run_id: str) -> "dict | None":
    """Return the full run row with result_json parsed to a dict, or None if not found."""
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id, conversation_id, message_id, query, result_json, via, created_at"
            " FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "conversation_id": row["conversation_id"],
            "message_id": row["message_id"],
            "query": row["query"],
            "result_json": json.loads(row["result_json"]),
            "via": row["via"],
            "created_at": row["created_at"],
        }
    finally:
        conn.close()


def get_effective_evidence(conv_id: str) -> "dict | None":
    """WO-9 Phase 5 — the EFFECTIVE dossier evidence for a conversation: the last REAL
    firm run's full ``result_json``, with its ``discover.dossier`` extended by the
    ``new_facts`` from every ``via="reinvoke"`` run chained to that same source run
    (ordered oldest -> newest, so repeated re-invocations accumulate). This is what
    "the dossier grows" means: the original run's stored ``result_json`` is NEVER
    rewritten (append-only, matching the harness trace / memory store convention
    elsewhere in this codebase) — the growth is computed here, on read.

    A "real firm run" is any run whose ``via`` is NEITHER "followup" NOR "reinvoke" —
    both of those are evidence-only / answer-only rows, never a source of evidence
    themselves.

    Returns ``{"result": <extended result dict>, "source_run_id": str}``, or ``None``
    if the conversation has no real firm run yet (unknown conversation, or one with
    only followup/reinvoke rows or no runs at all).
    """
    conv = get_conversation(conv_id)
    if conv is None:
        return None
    runs = conv.get("runs", [])  # ORDER BY created_at ASC (oldest -> newest)

    source_run_meta = None
    for run in runs:
        if run.get("via") not in ("followup", "reinvoke"):
            source_run_meta = run  # keep overwriting -> the LAST real firm run wins
    if source_run_meta is None:
        return None

    source_run_id = source_run_meta.get("id", "")
    full = get_run(source_run_id)
    if full is None:
        return None
    result = full.get("result_json")
    if not isinstance(result, dict):
        return None

    # Chain every via="reinvoke" row whose persisted source_run_id matches this run,
    # oldest -> newest (runs is already ASC-ordered).
    accumulated_facts: list = []
    for run in runs:
        if run.get("via") != "reinvoke":
            continue
        rfull = get_run(run.get("id", ""))
        if rfull is None:
            continue
        rresult = rfull.get("result_json")
        if not isinstance(rresult, dict) or rresult.get("source_run_id") != source_run_id:
            continue
        new_facts = rresult.get("new_facts")
        if isinstance(new_facts, list):
            accumulated_facts.extend(new_facts)

    if not accumulated_facts:
        return {"result": result, "source_run_id": source_run_id}

    import copy
    extended = copy.deepcopy(result)
    discover = extended.setdefault("discover", {})
    dossier = discover.get("dossier")
    discover["dossier"] = (dossier if isinstance(dossier, list) else []) + accumulated_facts
    return {"result": extended, "source_run_id": source_run_id}


def rename_conversation(conv_id: str, title: str) -> bool:
    """UPDATE title + bump updated_at. Returns True if a row was changed."""
    now = _now()
    conn = _get_conn()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
                (title, now, conv_id),
            )
        return cur.rowcount > 0
    finally:
        conn.close()


def set_starred(conv_id: str, starred: bool) -> bool:
    """UPDATE starred=1/0 + bump updated_at. Returns True if a row was changed."""
    now = _now()
    conn = _get_conn()
    try:
        with conn:
            cur = conn.execute(
                "UPDATE conversations SET starred = ?, updated_at = ? WHERE id = ?",
                (1 if starred else 0, now, conv_id),
            )
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_conversation(conv_id: str) -> bool:
    """Delete messages + runs for conv, then delete the conversation.

    Returns True if the conversation existed (and was deleted), False if not found.
    Uses explicit deletes (no CASCADE) to keep SQLite foreign-key setting irrelevant.
    """
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        if row is None:
            return False
        with conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            conn.execute("DELETE FROM runs WHERE conversation_id = ?", (conv_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        return True
    finally:
        conn.close()


def add_message(conv_id: str, role: str, content: str) -> str:
    """Insert a message row and bump conversations.updated_at. Returns the message id.

    role must be one of ('user', 'assistant', 'system'); raises ValueError for others.
    """
    if role not in ("user", "assistant", "system"):
        raise ValueError(
            f"Invalid role {role!r}. Must be one of 'user', 'assistant', 'system'."
        )
    mid = _new_id()
    now = _now()
    conn = _get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT INTO messages (id, conversation_id, role, content, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (mid, conv_id, role, content, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conv_id),
            )
    finally:
        conn.close()
    return mid


def save_run(
    conv_id: str,
    message_id: "str | None",
    query: str,
    result_dict: dict,
    via: str,
) -> str:
    """Serialise result_dict to JSON, insert a run row, bump conversations.updated_at.

    Returns the new run id.
    """
    rid = _new_id()
    now = _now()
    result_json = json.dumps(result_dict, default=str)
    conn = _get_conn()
    try:
        with conn:
            conn.execute(
                "INSERT INTO runs"
                " (id, conversation_id, message_id, query, result_json, via, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (rid, conv_id, message_id, query, result_json, via, now),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now, conv_id),
            )
    finally:
        conn.close()
    return rid
