"""Captured-EMET envelope store — the front end's REAL-EMET path (the session-bridge).

A captured envelope is one EMET dossier driven LIVE in the orchestrator's authenticated
BenchSci session (the `emet_protocol.md §7` shape: `candidate, emet_workflow, verdict,
evidence[], notes, chat_url, captured_at, provenance`) and frozen to JSON, keyed by the public
candidate identifier. These are **real `emet-live` facts** captured from a real session — public
PMIDs/DOIs only (data-boundary clean) — never fabricated.

The store lives at `sapphire-orchestrator/scenarios/emet_envelopes/<candidate>.json` (lowercased
candidate as the filename). `make_session_emet_handler(load_envelopes())` then injects them into
`run_live`: a COVERED candidate (one with a stored envelope) lands its real PMIDs; an UNCOVERED
candidate falls through the session handler to an honest abstain (`login_required` → escalate),
never a fabricated fact.

stdlib-only (json + pathlib) so it stays inside the engine import boundary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# scenarios/emet_envelopes/ lives next to this package (sapphire-orchestrator/).
_DIR = Path(__file__).resolve().parent.parent / "scenarios" / "emet_envelopes"


def envelopes_dir() -> Path:
    """The captured-envelope directory (override via $SAPPHIRE_EMET_ENVELOPES_DIR for tests)."""
    override = os.environ.get("SAPPHIRE_EMET_ENVELOPES_DIR")
    return Path(override) if override else _DIR


def load_envelopes(directory: str | os.PathLike | None = None) -> dict:
    """Load every captured envelope under `directory` (default: the store dir).

    Returns `{candidate: envelope}` keyed by each file's `candidate` field (falling back to the
    file stem, upper-cased, when the field is absent). A malformed/unreadable file is skipped
    silently — a bad capture must never crash a run; the candidate simply stays uncovered (the
    session handler then abstains honestly for it). Returns `{}` when the dir is absent.
    """
    d = Path(directory) if directory is not None else envelopes_dir()
    if not d.is_dir():
        return {}
    out: dict = {}
    for p in sorted(d.glob("*.json")):
        try:
            env = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue  # skip a malformed capture — never fabricate, never crash
        if not isinstance(env, dict):
            continue
        key = str(env.get("candidate") or p.stem).strip()
        if key:
            out[key] = env
    return out


def load_envelope_for(candidate: str,
                      directory: str | os.PathLike | None = None) -> dict | None:
    """Load the single captured envelope covering `candidate` (case-tolerant), or None.

    Used by the front-end bridge to auto-load ONLY the run's candidate, so an unrelated stored
    envelope never bleeds into an uncovered run. None ⇒ no capture for this candidate (the caller
    then lets the session handler abstain honestly).
    """
    cand = (candidate or "").strip()
    if not cand:
        return None
    envs = load_envelopes(directory)
    if cand in envs:
        return envs[cand]
    lc = {k.upper(): v for k, v in envs.items()}
    return lc.get(cand.upper())
