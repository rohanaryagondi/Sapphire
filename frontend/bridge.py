"""In-process bridge: the seam between the Chainlit UI and Sapphire's live firm.

`run(query, *, mock)` calls `live_engine.run_live(query, ctx=...)` in-process and returns
the raw result dict (the documented `run_live` contract — see
`sapphire-orchestrator/contracts/run_live_schema.md`). The engine is **stdlib-only**, so
importing it here pulls in NO third-party package — chainlit/pandas stay frontend-only and
never leak into the engine.

- `mock=True`  → the offline mock ctx (Demo profile): deterministic, $0, no external calls.
- `mock=False` → `ctx=None` (Live profile): real backends. `run_live` needs the `claude` CLI
  for the live persona/fact subagents; without it those agents **abstain honestly** (the run
  is degraded, never fabricated, never a crash).

`run` never propagates an exception: `run_live` is contracted not to raise, and we wrap the
call so that even an import/setup failure returns an honest error envelope the UI renders as
an abstain — not a traceback in the user's face.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

_ENGINE = Path(__file__).resolve().parents[1] / "sapphire-orchestrator"


def _ensure_engine_on_path() -> None:
    """Put the stdlib engine dir on sys.path. Called at CALL time (not just import) because
    Chainlit rebuilds sys.path between importing the app module and running the message
    handler — a module-level insert would be gone by the time `run()` executes (verified:
    onpath=False under chainlit). Idempotent.
    """
    if str(_ENGINE) not in sys.path:
        sys.path.insert(0, str(_ENGINE))


_ensure_engine_on_path()  # best-effort at import; run()/build_ctx re-ensure at call time


def build_ctx(mock: bool):
    """Demo → the offline mock ctx; Live → None (real backends)."""
    if not mock:
        return None
    _ensure_engine_on_path()
    from mock_ctx import build_mock_ctx
    return build_mock_ctx()


def _candidate_of(query: str) -> str:
    """The run's primary candidate (genes[0]) — the key the captured-envelope store is keyed on.

    Best-effort: any extractor failure returns "" (no candidate → no auto-loaded envelope → the
    session handler abstains honestly). Never raises into the run path.
    """
    try:
        _ensure_engine_on_path()
        from engagement import extract_entities
        ents = extract_entities(query or "")
        return ents["genes"][0] if ents.get("genes") else ""
    except Exception:
        return ""


def _resolve_emet_envelopes(query: str, emet_envelopes: dict | None) -> dict:
    """Resolve the captured EMET envelopes for this run.

    Precedence: an explicit `emet_envelopes` dict wins (used as-is). When `None`, AUTO-LOAD the
    single stored envelope covering the run's candidate from
    `sapphire-orchestrator/scenarios/emet_envelopes/<candidate>.json` (the session-bridge store)
    — so a front-end Live TSC2 run renders the real captured EMET dossier with zero wiring. No
    stored envelope for the candidate ⇒ `{}` (the session handler then abstains honestly; we
    never fabricate). Any load failure degrades to `{}` (never crashes the run).
    """
    if emet_envelopes is not None:
        return emet_envelopes
    try:
        _ensure_engine_on_path()
        from emet.envelopes import load_envelope_for
        cand = _candidate_of(query)
        env = load_envelope_for(cand) if cand else None
        return {cand: env} if env else {}
    except Exception:
        return {}


def _ctx_with_session_emet(mock: bool, envelopes: dict):
    """Build the run ctx, injecting the in-session EMET handler when envelopes are present.

    The session handler (backed by captured envelopes) is the front end's REAL-EMET path: for a
    COVERED candidate it lands real `emet-live` PMIDs; for an UNCOVERED one it abstains honestly.
    It is set ON the ctx so it WINS over `run_live`'s default (`claude -p`) handler — which
    `_wire_emet_handler` only `setdefault`s. With no envelopes we return `build_ctx(mock)`
    unchanged, so the `claude -p` path stays as the documented non-default fallback.

    Live (`mock=False`) has ctx=None: we materialise a fresh dict carrying ONLY the handler, and
    `run_live` `setdefault`s the rest (real moat / seams / Q-Models still load). Demo (`mock=True`)
    starts from the mock ctx and the session handler overwrites its mock EMET handler.
    """
    base = build_ctx(mock)
    if not envelopes:
        return base
    _ensure_engine_on_path()
    from emet.session_bridge import make_session_emet_handler
    ctx = dict(base) if base else {}
    ctx["emet_handler"] = make_session_emet_handler(envelopes)
    return ctx


def _error_envelope(query: str, exc: Exception) -> dict:
    """An honest, well-formed degraded result when the bridge itself can't run the firm.

    Shaped like a minimal run_live dict so the renderer treats it as an empty/abstained run,
    never a fabricated answer.
    """
    return {
        "query": query,
        "plan": {"deliverable": "", "disease": "", "modality": "",
                 "agents": [], "panel": []},
        "priors": [],
        "discover": {
            "dossier": [],
            "flags": {"VETO": [], "DIVERGENCE": [],
                      "KNOWN_UNKNOWNS": [f"bridge error: {type(exc).__name__}: {exc}"]},
            "status": "bridge-error",
            "agents": [],
        },
        "consult": {"round1": []},
        "synthesize": {
            "recommendation": "Unavailable — the firm could not be convened (bridge error).",
            "confidence": "none",
            "proposed_experiment": "",
            "entities": {},
        },
        "engagement_id": "",
        "reflection": {"engagement_id": "", "written": 0, "records": []},
        "_via": "bridge-error",
        "_bridge_error": f"{type(exc).__name__}: {exc}",
    }


def run(query: str, *, mock: bool = True, sequences: list | None = None,
        model: str | None = None, on_progress=None, simulate: bool = False,
        emet_envelopes: dict | None = None) -> dict:
    """Run the firm for `query` and return the run_live result dict (+ `_elapsed_s`).

    `emet_envelopes` is the front end's REAL-EMET path (the session-bridge). When a dict is
    supplied, or — when `None` — when a captured envelope for the run's candidate exists under
    `sapphire-orchestrator/scenarios/emet_envelopes/`, the in-session EMET handler
    (`make_session_emet_handler`) is wired onto the ctx and WINS over `run_live`'s default
    `claude -p` handler. A COVERED candidate (e.g. TSC2) then lands real `emet-live` PMIDs; an
    UNCOVERED candidate abstains honestly (the session handler returns login_required → the agent
    escalates → abstains) — never a fabricated fact. With no captured envelope the `claude -p`
    path remains the documented non-default fallback (it tool-fails / is too slow per Gate-5, so
    the session/captured envelope wins for covered candidates). `run_live` still `setdefault`s
    the rest of the ctx, so the real moat / seams / Q-Models load as usual.

    `simulate` (SAPPHIRE_SIMULATE_MODELS) replaces every claude-subagent's model reasoning
    (persona verdicts + claude fact agents) with a CLEARLY-LABELED 🧪 simulated stand-in
    (provenance `simulated`) — fast, for the demo, while real `claude -p` is slow. Real EMET /
    moat / seams / Q-Models stay genuinely REAL. The env is set + restored around this call.

    `on_progress(event)` is forwarded to `run_live` (live-run-visibility): it fires per
    milestone (plan, each Bucket-1 agent start/done, flags, each persona start/done, synthesis)
    so the caller can stream a live step tree. It runs on the worker thread that executes
    `run_live`; the UI handler is responsible for marshalling events back to its event loop.
    `None` ⇒ no progress (existing behavior).

    `sequences` is forwarded to `run_live` (the documented ASO-Design handoff: when ASO
    candidates are present they reach the aso-tox agent; `None` lets run_live extract any
    A/T/G/C tokens from the query itself).

    `model` (e.g. a haiku id) pins the LLM for every claude agent for the duration of THIS
    run, via the `CLAUDE_MODEL` env that `dispatch_claude` reads — the "cheap live" lever
    (real moat/EMET/seams/corpora, cheap reasoning). It is set and restored around the call
    (single-user local surface); a concurrent run could briefly observe it, which is acceptable
    here. `None` → the CLI default (existing Demo/Live behavior unchanged).

    Never raises. On a hard failure returns `_error_envelope`. Adds a single TOTAL wall-clock
    (`_elapsed_s`) — per-agent timing is NOT available from the contract and is never faked.
    """
    started = time.monotonic()
    _prev_model = os.environ.get("CLAUDE_MODEL")
    _prev_sim = os.environ.get("SAPPHIRE_SIMULATE_MODELS")
    try:
        _ensure_engine_on_path()
        if model:
            os.environ["CLAUDE_MODEL"] = model
        if simulate:
            os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        from live_engine import run_live
        envelopes = _resolve_emet_envelopes(query, emet_envelopes)
        result = run_live(query, sequences=sequences,
                          ctx=_ctx_with_session_emet(mock, envelopes),
                          on_progress=on_progress)
    except Exception as exc:  # defensive — run_live is designed not to raise
        result = _error_envelope(query, exc)
    finally:
        if model:
            if _prev_model is None:
                os.environ.pop("CLAUDE_MODEL", None)
            else:
                os.environ["CLAUDE_MODEL"] = _prev_model
        if simulate:
            if _prev_sim is None:
                os.environ.pop("SAPPHIRE_SIMULATE_MODELS", None)
            else:
                os.environ["SAPPHIRE_SIMULATE_MODELS"] = _prev_sim
    result["_elapsed_s"] = round(time.monotonic() - started, 2)
    result["_mock"] = bool(mock)
    result["_model"] = model or ""
    result["_simulated"] = bool(simulate)
    # Honest labeling: record which candidates this run had a captured-session EMET envelope for
    # (the real-EMET path). Empty ⇒ no covered candidate → EMET ran via the claude -p fallback (or
    # the mock handler in Demo). Never fabricated — derived from the resolved envelopes above.
    try:
        result["_emet_session"] = sorted(envelopes.keys())  # type: ignore[name-defined]
    except Exception:
        result["_emet_session"] = []
    return result


# Captured-scenario directory (real run_live outputs frozen for $0 deterministic replay).
_SCENARIOS = _ENGINE / "scenarios"


def replay(scenario: str = "tsc2_live_run") -> dict:
    """Load a frozen, real `run_live` capture for **$0 deterministic replay** (no model, no
    network). The captured dict is a real engagement (real moat + real EMET PMIDs + the live
    spread) — rendered identically to a live run; provenance/tier/flags preserved verbatim.
    Stamps `_via="replay"`, `_mock=False` (the facts are real, just frozen). On a missing/bad
    file returns an honest error envelope (never fabricates)."""
    import json
    _ensure_engine_on_path()
    path = _SCENARIOS / f"{scenario}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return _error_envelope(f"replay:{scenario}", exc)
    data["_via"] = "replay"
    data["_mock"] = False
    data["_replay"] = True
    data["_elapsed_s"] = 0.0
    return data


def available_replays() -> list:
    """List the frozen captured scenarios available for replay.

    Includes both the `*_live_run.json` captures and the `*_emet_session.json` session-bridge
    captures (a full `run_live` output with a captured EMET envelope injected — real moat + real
    EMET PMIDs + the spread, frozen for $0 deterministic replay).
    """
    if not _SCENARIOS.is_dir():
        return []
    stems = {p.stem for p in _SCENARIOS.glob("*_live_run.json")}
    stems |= {p.stem for p in _SCENARIOS.glob("*_emet_session.json")}
    return sorted(stems)
