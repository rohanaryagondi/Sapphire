"""frontend2 — a thin, STDLIB-ONLY front-end server for Sapphire's live firm.

WHY THIS EXISTS
---------------
Chainlit's fixed single-column React layout can't render Gavin's 3-pane chat-first
design or Hayes's agent-wing + attributed-findings without forking its React. We own
the design (`docs/design/console-ui/sapphire_chat.html`) and the engine
(`live_engine.run_live` returns a structured dict AND streams per-agent events via
`on_progress`), so this is a thin custom front end: full fidelity, no framework ceiling.

This server is **`http.server.ThreadingHTTPServer` + the Python standard library only** —
NO fastapi / flask / chainlit / any third-party package. The engine is stdlib-only and we
keep the whole front door stdlib so importing it pulls in nothing new. The Chainlit
`frontend/` stays untouched as the fallback.

ROUTES
------
- ``GET /``                       → ``static/index.html``
- ``GET /static/<path>``          → a file under ``static/`` (css/js/svg/…); path-traversal-safe.
- ``GET /api/replays``            → JSON list of available frozen replay scenarios.
- ``POST /api/run``               → **Server-Sent Events**. Body JSON ``{query, profile, structure?}``.
- ``GET /api/trace/<id>``         → the RAW engagement trace JSONL for engagement ``<id>``
  (``RohanOnly/engagements/<id>/trace.jsonl``) — every agent's inputs_hash, status,
  provenance, guardrails_run, repairs, output, elapsed_s. 404 honestly if absent.
- ``GET /api/runs/<id>``          → the COMPLETE cached ``run_live`` result dict for engagement
  ``<id>`` (the same dict the ``result`` SSE frame carried), or 404 if not cached.

FULL BACKEND ACCESS (for Demo Claudes — the hard requirement)
-------------------------------------------------------------
A Demo Claude consumes structured data, NEVER a screenshot of the UI:
- ``POST /api/run`` (SSE) gives the live per-agent events AND, in the ``result`` frame, the
  COMPLETE ``run_live`` dict — every dossier fact with ALL fields
  (value/field/tier/provenance/source/plane/flag), the flags (VETO/DIVERGENCE/KNOWN_UNKNOWNS),
  the FULL roundtable spread (every persona's stance/conviction/rationale), synthesis, plan,
  engagement_id, _via. No truncation, no summarisation.
- ``GET /api/trace/<engagement_id>`` returns the raw append-only trace JSONL for that run.
- ``GET /api/runs/<engagement_id>`` returns the last full result dict (server-side cache).
See ``README.md`` → "Full backend access for Demo Claudes".

THE SSE CONTRACT (also documented in README.md)
-----------------------------------------------
``POST /api/run`` streams ``text/event-stream``. The firm runs in the request handler
thread; ``bridge.run``'s ``on_progress`` callback (fired on that same thread) pushes each
milestone onto a thread-safe ``queue.Queue`` that the writer drains to the socket. Events:

- ``event: open``  / ``data: {profile, query, via}``       — emitted first, before the run.
- ``event: progress`` / ``data: <run_live progress event>`` — one per milestone
  (``stage`` ∈ plan|bucket1|flags|roundtable|synthesis; ``phase`` ∈ start|done; +agent_id,
  status, provenance, n_facts, elapsed_s, …). Forwarded verbatim from the engine.
- ``event: result`` / ``data: <full run_live dict>``        — the complete dossier, once
  the run returns. This dict is the documented ``run_live`` contract (+ the bridge's
  ``_via`` / ``_mock`` / ``_elapsed_s`` / ``_emet_session`` stamps).
- ``event: error`` / ``data: {error}``                      — only on a hard failure the
  bridge couldn't absorb. (``bridge.run`` is contracted not to raise and returns an honest
  degraded envelope instead, so this is the last-resort net — the UI shows an abstain, never
  a 500 crash.)
- ``event: done`` / ``data: {}``                            — always last; closes the stream.

PROFILES (mapped to ``bridge.run`` kwargs — honesty preserved)
--------------------------------------------------------------
- ``demo``     → ``mock=True``               : offline mock backends, $0, deterministic.
- ``simulate`` → ``mock=False, simulate=True``: REAL moat/EMET/seams/Q-Models; persona +
  claude-fact reasoning is 🧪 simulated (clearly labeled, never a real verdict).
- ``live``     → ``mock=False``               : real backends; claude subagents shell out to
  the CLI (absent ⇒ they abstain honestly).
- ``replay``   → ``bridge.replay(scenario)``  : a frozen REAL capture, $0, no model/network.

DATA-BOUNDARY / HONESTY
-----------------------
This server never invents facts. It forwards the engine's result verbatim — tier,
provenance, plane, abstentions and flags pass through unchanged. The engine enforces the
data boundary (only public identifiers leave); secrets (Boltz/EMET creds) are read by the
seams from ``RohanOnly/`` at runtime and are never read or logged here.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import queue
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
_STATIC = _HERE / "static"
_FRONTEND = _REPO / "frontend"  # we REUSE frontend/bridge.py (the in-process run_live seam)

# Make the existing bridge importable. We do NOT import chainlit — bridge.py is stdlib-only
# (it lazy-imports the engine; chainlit/pandas live in frontend/main.py, never touched here).
for _p in (str(_FRONTEND), str(_REPO / "sapphire-orchestrator")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import bridge  # noqa: E402  the in-process run_live seam (stdlib-only)

# A frozen capture to replay per profile=="replay". The session-bridge capture is the richest
# (real moat + 9 real EMET PMIDs + the spread). Overridable via the request's `scenario`.
_DEFAULT_REPLAY = "tsc2_emet_session"

# Sentinels on the SSE queue.
_DONE = object()

# Server-side cache of the last full run_live result per engagement_id (for GET /api/runs/<id>).
# Bounded so a long-lived server doesn't grow unbounded; the latest runs are what a Demo Claude
# fetches. Guarded by a lock (the SSE writer thread populates it; GET handlers read it).
_RESULTS: "dict[str, dict]" = {}
_RESULTS_ORDER: "list[str]" = []
_RESULTS_LOCK = threading.Lock()
_RESULTS_MAX = 64


def _cache_result(result: dict) -> None:
    """Cache a completed run by its engagement_id (bounded LRU-ish). Best-effort: a result
    without an engagement_id (e.g. a bridge-error envelope) is simply not cached."""
    eid = (result or {}).get("engagement_id") or ""
    if not eid:
        return
    with _RESULTS_LOCK:
        if eid in _RESULTS:
            _RESULTS_ORDER.remove(eid)
        _RESULTS[eid] = result
        _RESULTS_ORDER.append(eid)
        while len(_RESULTS_ORDER) > _RESULTS_MAX:
            _RESULTS.pop(_RESULTS_ORDER.pop(0), None)


def _engagements_dir() -> Path:
    """Resolve the engagement-trace base dir, honouring the same SAPPHIRE_ENGAGEMENTS_DIR
    override the harness trace writer uses (so tests + the front end agree), else the repo's
    canonical `RohanOnly/engagements/`."""
    import os
    override = os.environ.get("SAPPHIRE_ENGAGEMENTS_DIR")
    if override:
        return Path(override)
    return _REPO / "RohanOnly" / "engagements"


# A valid engagement id is `eng_…` (alnum/_/-): used to reject path traversal on /api/trace + /api/runs.
import re as _re  # noqa: E402

_EID_RE = _re.compile(r"^[A-Za-z0-9_-]+$")


def _profile_kwargs(profile: str) -> dict:
    """Map a UI profile string → bridge.run kwargs. Unknown ⇒ demo (safe, offline, $0)."""
    if profile == "live":
        return {"mock": False}
    if profile == "simulate":
        # REAL backends; claude-subagent reasoning is 🧪 simulated (fast, clearly labeled).
        return {"mock": False, "simulate": True}
    return {"mock": True}  # "demo" and anything unrecognised


def _sse(event: str, data) -> bytes:
    """Encode one Server-Sent Event frame. ``data`` is JSON-serialised."""
    payload = json.dumps(data, default=str, ensure_ascii=False)
    # An SSE `data:` line cannot contain a raw newline; JSON has none (no indent) so one
    # line is safe, but be defensive and split on any embedded newline per the spec.
    lines = "".join(f"data: {chunk}\n" for chunk in payload.split("\n"))
    return f"event: {event}\n{lines}\n".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    server_version = "SapphireFrontend2/1.0"
    protocol_version = "HTTP/1.1"  # keep-alive + chunked-free streaming with explicit flush

    # Quiet the default per-request stderr logging (keep our own concise line).
    def log_message(self, fmt, *args):  # noqa: D401
        sys.stderr.write(f"[frontend2] {self.address_string()} {fmt % args}\n")

    # ----------------------------------------------------------------- GET
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "":
            return self._serve_file(_STATIC / "index.html")
        if path == "/api/replays":
            return self._send_json(200, {"replays": _safe_replays()})
        if path.startswith("/api/trace/"):
            return self._serve_trace(path[len("/api/trace/"):])
        if path.startswith("/api/runs/"):
            return self._serve_run(path[len("/api/runs/"):])
        # Conversation history routes (Wave-1 persistence).
        if path == "/api/conversations":
            return self._serve_conversations_list()
        if path.startswith("/api/conversations/"):
            conv_id = path[len("/api/conversations/"):]
            return self._serve_conversation_detail(conv_id)
        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            target = (_STATIC / rel).resolve()
            # Path-traversal guard: the resolved target must stay inside _STATIC.
            if _STATIC not in target.parents and target != _STATIC:
                return self._send_json(403, {"error": "forbidden"})
            return self._serve_file(target)
        return self._send_json(404, {"error": "not found"})

    # ----------------------------------------------------------------- POST
    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return self._send_json(400, {"error": "invalid JSON body"})
        if path == "/api/run":
            query = (body.get("query") or "").strip()
            profile = (body.get("profile") or "demo").strip()
            scenario = (body.get("scenario") or _DEFAULT_REPLAY).strip()
            model = (body.get("model") or "").strip()
            conversation_id = (body.get("conversation_id") or "").strip() or None
            if not query and profile != "replay":
                return self._send_json(400, {"error": "empty query"})
            self._stream_run(query, profile, scenario, model,
                             conversation_id=conversation_id)
        elif path == "/api/conversations":
            try:
                import store as _store_mod
                title = body.get("title") or "New conversation"
                cid = _store_mod.create_conversation(title)
                return self._send_json(200, {"id": cid})
            except Exception as exc:
                return self._send_json(500, {"error": str(exc)})
        else:
            return self._send_json(404, {"error": "not found"})

    # ---------------------------------------------------------------- PATCH
    def do_PATCH(self) -> None:
        path = self.path.split("?", 1)[0]
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return self._send_json(400, {"error": "invalid JSON body"})
        if path.startswith("/api/conversations/"):
            conv_id = path[len("/api/conversations/"):]
            try:
                import store as _store_mod
                if "title" in body:
                    _store_mod.rename_conversation(conv_id, body["title"])
                elif "starred" in body:
                    _store_mod.set_starred(conv_id, bool(body["starred"]))
                return self._send_json(200, {"ok": True})
            except Exception as exc:
                return self._send_json(500, {"error": str(exc)})
        return self._send_json(404, {"error": "not found"})

    # --------------------------------------------------------------- DELETE
    def do_DELETE(self) -> None:
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/conversations/"):
            conv_id = path[len("/api/conversations/"):]
            try:
                import store as _store_mod
                deleted = _store_mod.delete_conversation(conv_id)
                if deleted:
                    return self._send_json(200, {"ok": True})
                return self._send_json(404, {"error": "not found"})
            except Exception as exc:
                return self._send_json(500, {"error": str(exc)})
        return self._send_json(404, {"error": "not found"})

    # ------------------------------------------------------- SSE streaming
    def _stream_run(self, query: str, profile: str, scenario: str, model: str = "",
                    conversation_id: "str | None" = None) -> None:
        """Run the firm and stream progress + result as SSE.

        The run executes on a worker thread; its ``on_progress`` callback (fired on that
        worker) enqueues events onto a thread-safe ``queue.Queue``. THIS handler thread
        drains the queue and writes each frame to the socket, flushing after every write so
        the browser renders the trace LIVE. Honest-degrade: a hard failure becomes an
        ``error`` frame (never a 500), always followed by ``done``.
        """
        # Close the connection when the stream ends. SSE has no Content-Length and is not
        # chunked here; a keep-alive socket would leave a blocking reader (e.g. urllib) waiting
        # forever for an EOF that never comes. `Connection: close` + close_connection=True make
        # the socket close cleanly after `done` — the browser's incremental reader still gets
        # every frame as it flushes, then a clean end-of-stream.
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")  # disable proxy buffering if any
        self.end_headers()

        via = "replay" if profile == "replay" else (
            "engine-demo" if profile == "demo" else "engine-live")
        self._write(_sse("open", {"profile": profile, "query": query, "via": via}))

        evq: "queue.Queue" = queue.Queue()

        def on_progress(ev):  # fired on the worker thread
            evq.put(("progress", ev))

        def worker():
            try:
                if profile == "replay":
                    result = bridge.replay(scenario)
                else:
                    result = bridge.run(query, on_progress=on_progress,
                                        model=(model or None),
                                        **_profile_kwargs(profile))
                _cache_result(result)  # so GET /api/runs/<engagement_id> can return it
                evq.put(("result", result))
            except Exception as exc:  # bridge.run is contracted not to raise; last-resort net
                evq.put(("error", {"error": f"{type(exc).__name__}: {exc}",
                                    "trace": traceback.format_exc()}))
            finally:
                evq.put((_DONE, None))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        # Drain until the worker signals done. Every write is flushed for live streaming.
        try:
            while True:
                kind, payload = evq.get()
                if kind is _DONE:
                    break
                if kind == "result":
                    # best-effort — store failure must NOT break the SSE stream
                    try:
                        import store as _store_mod
                        cid = conversation_id
                        if cid is None:
                            cid = _store_mod.create_conversation(
                                query[:80] or "Sapphire run"
                            )
                        msg_id = _store_mod.add_message(cid, "user", query)
                        run_id = _store_mod.save_run(cid, msg_id, query, payload, via)
                        if isinstance(payload, dict):
                            payload["_conversation_id"] = cid
                            payload["_run_id"] = run_id
                    except Exception as _store_exc:
                        import sys as _sys
                        print(
                            f"[store] save failed (non-fatal): {_store_exc}",
                            file=_sys.stderr,
                        )
                if not self._write(_sse(kind, payload)):
                    break  # client disconnected — stop writing
        finally:
            self._write(_sse("done", {}))
            t.join(timeout=1.0)

    # ------------------------------------------------------------- helpers
    def _write(self, data: bytes) -> bool:
        """Write + flush to the client. Returns False if the client has disconnected."""
        try:
            self.wfile.write(data)
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError, ValueError):
            return False

    def _serve_file(self, target: Path) -> None:
        if not target.is_file():
            return self._send_json(404, {"error": "not found"})
        ctype, _ = mimetypes.guess_type(str(target))
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self._write(data)

    def _serve_conversations_list(self) -> None:
        """GET /api/conversations → {conversations: [...]} from the persistent store."""
        try:
            import store as _store_mod
            return self._send_json(200, {"conversations": _store_mod.list_conversations()})
        except Exception as exc:
            return self._send_json(500, {"error": str(exc)})

    def _serve_conversation_detail(self, conv_id: str) -> None:
        """GET /api/conversations/<id> → full {conversation, messages, runs} dict or 404."""
        try:
            import store as _store_mod
            conv = _store_mod.get_conversation(conv_id)
            if conv is None:
                return self._send_json(404, {"error": "not found"})
            return self._send_json(200, conv)
        except Exception as exc:
            return self._send_json(500, {"error": str(exc)})

    def _serve_trace(self, eid: str) -> None:
        """GET /api/trace/<engagement_id> → the RAW append-only trace JSONL for that run.

        FULL BACKEND ACCESS: returns the bytes of `RohanOnly/engagements/<id>/trace.jsonl`
        verbatim (Content-Type application/x-ndjson) — every harness event (inputs_hash, status,
        provenance, guardrails_run, repairs, output, elapsed_s). A Demo Claude parses this; it
        never screenshots. 404 honestly when the engagement has no trace on disk."""
        eid = eid.split("?", 1)[0].strip("/")
        if not eid or not _EID_RE.match(eid):
            return self._send_json(400, {"error": "invalid engagement id"})
        path = (_engagements_dir() / eid / "trace.jsonl").resolve()
        base = _engagements_dir().resolve()
        # Path-traversal guard: the resolved file must live under the engagements dir.
        if base not in path.parents:
            return self._send_json(403, {"error": "forbidden"})
        if not path.is_file():
            return self._send_json(404, {"error": f"no trace for engagement {eid}"})
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self._write(data)

    def _serve_run(self, eid: str) -> None:
        """GET /api/runs/<engagement_id> → the COMPLETE cached run_live result dict for that run.

        FULL BACKEND ACCESS: the exact dict the `result` SSE frame carried (no truncation),
        from the in-process bounded cache. 404 if this server hasn't run/cached that id."""
        eid = eid.split("?", 1)[0].strip("/")
        if not eid or not _EID_RE.match(eid):
            return self._send_json(400, {"error": "invalid engagement id"})
        with _RESULTS_LOCK:
            result = _RESULTS.get(eid)
        if result is None:
            return self._send_json(404, {"error": f"no cached run for engagement {eid}"})
        return self._send_json(200, result)

    def _send_json(self, code: int, obj) -> None:
        data = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self._write(data)


def _safe_replays() -> list:
    try:
        return bridge.available_replays()
    except Exception:
        return []


def serve(host: str = "127.0.0.1", port: int = 8100) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Sapphire frontend2 → http://{host}:{port}  (stdlib-only; engine via frontend/bridge.py)")
    print("  profiles: demo (offline $0) · simulate (real facts, 🧪 reasoning) · live · replay")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sapphire frontend2 (stdlib-only SSE server)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8100)
    args = ap.parse_args()
    serve(host=args.host, port=args.port)
