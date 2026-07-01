"""EMET FILE-BRIDGE handler — live EMET without Playwright / auto-login.

The detached-`claude -p` runner (`handler._default_runner`) drives its OWN Playwright browser,
so it cannot reach the user's authenticated BenchSci session and fights the Chrome profile lock.
This handler takes a different path: a **separate Claude-in-Chrome session** (run by the user in
their already-authenticated browser) answers EMET requests through a shared file queue. Sapphire
writes a request line; that session appends a response line; the handler polls for it.

Protocol (shared dir ``RohanOnly/emet_bridge/`` — gitignored under RohanOnly/)
----------------------------------------------------------------------------
- ``requests.jsonl``  — Sapphire APPENDS one JSON per line::

      {"id": <uuid>, "query": <str>, "gene": <str|null>, "ts": <iso8601>}

- ``responses.jsonl`` — the EMET (Claude-in-Chrome) session APPENDS one JSON per line::

      {"id": <uuid>, "status": "ok"|"empty"|"error",
       "evidence": <markdown str>, "citations": [<str>, ...], "ts": <iso8601>}

  A request is answered once its ``id`` appears in ``responses.jsonl``.

Honesty / data boundary
-----------------------
- Only PUBLIC identifiers cross to EMET (gene symbol, disease/target term) — the same rule the
  Playwright runner obeys. The ``query`` and ``gene`` are built from the run's public inputs only.
- On ``status == "ok"`` the handler returns ONLY what the response actually holds — the evidence
  markdown as one cited **T2** fact and each supplied citation as its own cited T2 fact. It never
  invents a fact or a citation.
- On timeout / ``status == "error"`` / ``status == "empty"`` (or a missing/blank evidence body) the
  handler returns an HONEST ABSTAIN: a schema-valid findings envelope with an EMPTY ``facts`` list
  and provenance ``emet-live-bridge``. No fabricated facts, and it NEVER raises — an EMET hiccup
  must not crash the firm; the orchestrator slots a zero-fact EMET result as an honest no-result.

The provenance label on every emitted fact is ``emet-live-bridge`` (external plane) so a bridge
fact is always distinguishable from a Playwright-driven ``emet-live`` fact in the trace.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

# RohanOnly/emet_bridge/ — resolve relative to the repo root (two levels up from this package).
_ROOT = Path(__file__).resolve().parents[2]
PROVENANCE = "emet-live-bridge"

_DEFAULT_TIMEOUT_S = 180
_DEFAULT_POLL_S = 2.0
_TIMEOUT_FLOOR_S = 5


def bridge_dir() -> Path:
    """The shared bridge directory. ``$SAPPHIRE_EMET_BRIDGE_DIR`` overrides (used by tests)."""
    override = (os.environ.get("SAPPHIRE_EMET_BRIDGE_DIR") or "").strip()
    return Path(override) if override else (_ROOT / "RohanOnly" / "emet_bridge")


def _timeout_s() -> int:
    """Poll timeout in seconds. ``$SAPPHIRE_EMET_BRIDGE_TIMEOUT_S`` overrides; default 180, floor 5.

    A bad/blank value falls back to the default so a typo can't disable the timeout entirely.
    """
    raw = os.environ.get("SAPPHIRE_EMET_BRIDGE_TIMEOUT_S")
    try:
        return max(_TIMEOUT_FLOOR_S, int(raw))
    except (ValueError, TypeError):
        return _DEFAULT_TIMEOUT_S


def _poll_s() -> float:
    """Poll interval in seconds. ``$SAPPHIRE_EMET_BRIDGE_POLL_S`` overrides; default ~2s, floor 0.05.

    Exposed mainly so tests (which pre-write the response) can poll fast without a real wait.
    """
    raw = os.environ.get("SAPPHIRE_EMET_BRIDGE_POLL_S")
    try:
        return max(0.05, float(raw))
    except (ValueError, TypeError):
        return _DEFAULT_POLL_S


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _candidate(inputs: dict) -> str:
    """The public candidate identifier for the run (candidate | target | gene). Public only."""
    d = inputs or {}
    return str(d.get("candidate") or d.get("target") or d.get("gene") or "").strip()


def _query_text(inputs: dict) -> str:
    """Build the EMET query string from PUBLIC inputs only (never internal scores/data)."""
    d = inputs or {}
    q = str(d.get("question") or d.get("query") or d.get("workflow") or "").strip()
    cand = _candidate(d)
    if q and cand and cand.lower() not in q.lower():
        return f"{q} (candidate: {cand})"
    return q or cand


def _abstain(candidate: str) -> dict:
    """An HONEST, schema-valid EMET findings envelope with NO facts (timeout/error/empty).

    Zero facts = no evidence found via the bridge; the orchestrator treats it as an honest
    no-result, never a fabricated fact. Never raises."""
    return {"candidate": candidate, "facts": [], "provenance": PROVENANCE}


def _read_response(responses_path: Path, req_id: str) -> dict | None:
    """Return the FIRST response line whose ``id`` matches ``req_id``, or None if not present.

    Malformed lines are skipped silently — a bad line from the peer session must never crash the
    poll (never fabricate, never raise). Missing file → None (not yet answered)."""
    try:
        text = responses_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (ValueError, TypeError):
            continue  # skip a malformed response line
        if isinstance(obj, dict) and str(obj.get("id") or "") == req_id:
            return obj
    return None


def _normalize_response(resp: dict, candidate: str) -> dict:
    """Map a bridge response → a findings envelope. Only what the response HOLDS; never fabricate.

    ``status == "ok"`` with a non-empty evidence body → the evidence markdown as one cited T2 fact
    plus each supplied citation as its own cited T2 fact. Anything else (error / empty / blank
    evidence) → honest abstain (empty facts)."""
    status = str(resp.get("status") or "").strip().lower()
    evidence = str(resp.get("evidence") or "").strip()
    if status != "ok" or not evidence:
        return _abstain(candidate)

    facts = [{"value": evidence, "source": "EMET (Claude-in-Chrome bridge)",
              "tier": "T2", "provenance": PROVENANCE}]
    citations = resp.get("citations") or []
    if isinstance(citations, (list, tuple)):
        for c in citations:
            c = str(c or "").strip()
            if c:
                facts.append({"value": f"Cited source: {c}", "source": c,
                              "tier": "T2", "provenance": PROVENANCE})
    return {"candidate": candidate, "facts": facts, "provenance": PROVENANCE}


def _append_request(requests_path: Path, req: dict) -> None:
    """Append one request line (JSON + newline). Creates the file if absent."""
    with requests_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(req, ensure_ascii=False) + "\n")


def make_emet_bridge_handler(*, sleep=time.sleep, clock=time.monotonic):
    """Return a 2-arg ``(contract, inputs)`` EMET handler backed by the file bridge.

    Signature matches the seam the harness's ``emet-playwright`` dispatch calls (same as
    ``emet.make_emet_handler``). ``sleep`` / ``clock`` are injectable so tests never wait on a
    real clock. The handler NEVER raises: any failure degrades to an honest zero-fact abstain.
    """
    def _handler(contract, inputs):
        candidate = _candidate(inputs)
        try:
            d = bridge_dir()
            d.mkdir(parents=True, exist_ok=True)
            requests_path = d / "requests.jsonl"
            responses_path = d / "responses.jsonl"

            req_id = str(uuid.uuid4())
            req = {"id": req_id, "query": _query_text(inputs),
                   "gene": (candidate or None), "ts": _now_iso()}
            _append_request(requests_path, req)

            timeout = _timeout_s()
            poll = _poll_s()
            deadline = clock() + timeout
            # Poll for the matching response id until it lands or we time out.
            while True:
                resp = _read_response(responses_path, req_id)
                if resp is not None:
                    return _normalize_response(resp, candidate)
                if clock() >= deadline:
                    return _abstain(candidate)     # timeout → honest abstain
                sleep(poll)
        except Exception:
            # Defensive: an unexpected I/O / filesystem error must NEVER crash the firm. Abstain
            # honestly (no fabricated facts) instead of propagating.
            return _abstain(candidate)

    return _handler
