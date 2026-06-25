"""In-session EMET orchestration (the approved live-demo mechanism, dev/HELP.md → option (c)).

The detached `claude -p` EMET runner (`handler._default_runner`) spawns its OWN Playwright
browser, so it cannot inherit the interactive session's already-authenticated BenchSci tabs and
fights the Chrome profile lock — hence it honestly abstains when it lands on the login screen.

This bridge takes the other path: the **orchestrator drives EMET inside its own authenticated
session** (the browser the user logged into), captures the resulting EMET envelope(s) per
candidate, and injects them into `run_live` through the EXISTING `make_emet_handler(runner=...)`
seam. No subprocess, no profile-lock fight, no fabrication:

    # orchestrator (in its authenticated session) drives EMET per the emet-runner skill and
    # captures one envelope per candidate (public identifiers only):
    envelopes = {"TSC2": {<EMET envelope with real PMIDs>}}
    ctx = {"emet_handler": make_session_emet_handler(envelopes), ...}
    result = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=ctx)
    # run_live's emet-runner agent now consumes the REAL session evidence → real PMIDs land.

`run_live` only wires its default (abstaining) handler when the caller didn't supply one
(`_wire_emet_handler` uses setdefault), so a `ctx["emet_handler"]` from this bridge wins.

Honesty / boundary:
- A candidate with **no captured envelope** → the runner signals abstain (`{"login_required": true}`
  → the handler escalates → the agent abstains). We NEVER fabricate evidence for an uncovered
  candidate.
- EMET is the **external plane**: only public identifiers (gene symbol / protein / SMILES / disease
  term) are ever sent to EMET; the captured envelope carries cited public PMIDs/DOIs only.
- The session lives **in-process** (no authenticated profile written to disk) — the credential-at-rest
  concern Head Claude flagged for the shared `--user-data-dir` fallback does not apply here.
"""
from __future__ import annotations

from .handler import make_emet_handler


def _candidate_key(inputs: dict) -> str:
    return str((inputs or {}).get("candidate") or (inputs or {}).get("target") or "").strip()


def make_session_emet_handler(envelopes: dict):
    """Return a 2-arg `(contract, inputs)` EMET handler backed by captured session envelopes.

    `envelopes` maps a candidate identifier → its captured EMET envelope (the
    `emet_protocol.md §7` shape: `candidate, emet_workflow, verdict, evidence[], notes, chat_url,
    captured_at, provenance`). Lookup is case-tolerant on the candidate. No match → honest abstain.
    """
    envelopes = envelopes or {}
    # Case-tolerant index without losing the original keys.
    _index = {}
    for k, v in envelopes.items():
        _index[str(k).strip()] = v
        _index[str(k).strip().upper()] = v

    def _runner(inputs):
        cand = _candidate_key(inputs)
        env = _index.get(cand) or _index.get(cand.upper())
        if not env:
            # No captured session evidence for this candidate → abstain honestly, never fabricate.
            return {"login_required": True}
        return env

    return make_emet_handler(runner=_runner)
