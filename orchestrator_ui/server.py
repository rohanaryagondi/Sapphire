"""orchestrator_ui/server.py — stdlib SSE server on port :8100 for the LLM orchestrator demo.

Spawns `claude -p "<query>"` with the Sapphire orchestrator SKILL.md as the system prompt
and streams its output as Server-Sent Events to the browser.

Routes:
  GET  /             → orchestrator_ui/static/index.html
  GET  /static/<path>  → static files (path-traversal safe)
  POST /api/run {query} → SSE stream of tool calls + final result
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent                    # /tmp/demo-polish (worktree root)
_STATIC = _HERE / "static"
_SKILL_PATH = _REPO / ".claude" / "skills" / "sapphire-orchestrate" / "SKILL.md"
_CLAUDE_BIN = "/Users/rohanaryagondi/.local/bin/claude"

# The real repo root — for SAPPHIRE_MOAT_DB since the worktree lacks RohanOnly/
_REAL_REPO = Path("/Users/rohanaryagondi/Desktop/Projects/Quiver/sapphire-capability-map")
_MOAT_DB = _REAL_REPO / "RohanOnly" / "moat" / "moat.sqlite"

# Sentinels
_DONE = object()


def _load_skill() -> str:
    """Load the SKILL.md system prompt. Returns empty string if absent (honest fallback)."""
    try:
        return _SKILL_PATH.read_text(encoding="utf-8")
    except Exception:
        return ""


def _sse(event: str, data) -> bytes:
    """Encode one Server-Sent Event frame."""
    payload = json.dumps(data, default=str, ensure_ascii=False)
    lines = "".join(f"data: {chunk}\n" for chunk in payload.split("\n"))
    return f"event: {event}\n{lines}\n".encode("utf-8")


def _parse_json_block(text: str) -> dict | None:
    """Extract and parse the first ```json ... ``` block from a string."""
    m = re.search(r'```json\s*([\s\S]*?)\s*```', text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "SapphireOrchUI/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"[orchestrator_ui] {self.address_string()} {fmt % args}\n")

    # ----------------------------------------------------------------- GET
    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path in ("/", ""):
            return self._serve_file(_STATIC / "index.html")
        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            target = (_STATIC / rel).resolve()
            # Path-traversal guard
            if _STATIC not in target.parents and target != _STATIC:
                return self._send_json(403, {"error": "forbidden"})
            return self._serve_file(target)
        return self._send_json(404, {"error": "not found"})

    # ----------------------------------------------------------------- POST
    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/run":
            return self._send_json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            return self._send_json(400, {"error": "invalid JSON body"})
        query = (body.get("query") or "").strip()
        if not query:
            return self._send_json(400, {"error": "empty query"})
        self._stream_run(query)

    # ------------------------------------------------------- SSE streaming
    def _stream_run(self, query: str) -> None:
        """Spawn claude -p and stream events as SSE."""
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        skill_content = _load_skill()

        import os
        env = os.environ.copy()
        # Point moat client to the real DB even from the worktree
        if _MOAT_DB.exists():
            env["SAPPHIRE_MOAT_DB"] = str(_MOAT_DB)

        cmd = [
            _CLAUDE_BIN,
            "-p", query,
            "--append-system-prompt", skill_content,
            "--output-format", "stream-json",
            "--verbose",
            "--allowedTools", "Bash",
            "--add-dir", str(_REPO),
            "--dangerously-skip-permissions",
        ]

        evq: "list" = []
        lock = threading.Lock()
        finished = threading.Event()

        def worker():
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=str(_REPO),
                    text=True,
                    bufsize=1,
                    env=env,
                )
                for line in proc.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    ev_type = ev.get("type", "")

                    if ev_type == "assistant":
                        msg = ev.get("message", {})
                        for block in (msg.get("content") or []):
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") == "tool_use":
                                tool_name = block.get("name", "")
                                tool_input = block.get("input", {})
                                cmd_str = str(tool_input.get("command", ""))
                                if "moat" in cmd_str.lower():
                                    label = "→ moat"
                                elif "emet" in cmd_str.lower():
                                    label = "→ emet"
                                elif "boltz" in cmd_str.lower():
                                    label = "→ boltz"
                                else:
                                    label = f"→ {tool_name}"
                                with lock:
                                    evq.append(_sse("trace", {
                                        "type": "tool_call",
                                        "label": label,
                                        "tool": tool_name,
                                        "input": tool_input,
                                    }))
                            elif block.get("type") == "text":
                                text = block.get("text", "")
                                if text.strip():
                                    with lock:
                                        evq.append(_sse("trace", {
                                            "type": "text",
                                            "text": text[:2000],
                                        }))

                    elif ev_type == "result":
                        result_text = ev.get("result", "")
                        parsed = _parse_json_block(result_text)
                        if parsed:
                            with lock:
                                evq.append(_sse("result", parsed))
                        else:
                            with lock:
                                evq.append(_sse("result", {
                                    "synthesis": result_text,
                                    "ranked_genes": [],
                                    "plan_steps": [],
                                }))

                proc.wait()
                if proc.returncode not in (0, None):
                    stderr_out = proc.stderr.read() if proc.stderr else ""
                    if stderr_out:
                        with lock:
                            evq.append(_sse("trace", {
                                "type": "text",
                                "text": f"[claude exited {proc.returncode}] {stderr_out[:500]}",
                            }))
            except Exception as exc:
                with lock:
                    evq.append(_sse("error", {"error": str(exc)}))
            finally:
                finished.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        # Drain events as they arrive
        sent = 0
        while not finished.is_set() or sent < len(evq):
            with lock:
                batch = evq[sent:]
                sent += len(batch)
            for frame in batch:
                if not self._write(frame):
                    finished.set()
                    break
            if not batch:
                # Wait briefly before polling again
                finished.wait(timeout=0.05)

        self._write(_sse("done", {}))
        t.join(timeout=2.0)

    # ------------------------------------------------------------- helpers
    def _write(self, data: bytes) -> bool:
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

    def _send_json(self, code: int, obj) -> None:
        data = json.dumps(obj, default=str).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self._write(data)


def serve(host: str = "127.0.0.1", port: int = 8100) -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    print(f"Sapphire Orchestrator UI → http://{host}:{port}")
    print(f"  claude: {_CLAUDE_BIN}")
    print(f"  skill:  {_SKILL_PATH}")
    print(f"  moat:   {_MOAT_DB} ({'ok' if _MOAT_DB.exists() else 'absent'})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Sapphire Orchestrator UI (stdlib SSE server)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8100)
    args = ap.parse_args()
    serve(host=args.host, port=args.port)
