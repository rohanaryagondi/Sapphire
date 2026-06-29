#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sapphire bridge — serves the site AND runs the in-process harnessed firm for fresh engagements.

    python sapphire-orchestrator/serve.py            # http://localhost:8077  (Console = main site)

How it works — two primary paths:
  (a) Fresh engagements (POST /api/chat and GET /api/run default): the query is dispatched
      IN-PROCESS to `live_engine.run_live` — the fully harnessed firm (guard-enforced,
      provenance-stamped, traced, via=engine-live). No subprocess needed; this is the real
      front door. Degrades honestly to a plan-only envelope if run_live raises.
  (b) Follow-up grounding (POST /api/chat with an existing dossier) and the labeled
      reconstruction fallback (GET /api/run?mode=claude): these call `claude -p` headless on
      your **subscription** (no API key). Claude reconstructs facts from training; the UI
      labels these as "claude-subscription", not live-EMET. If the claude CLI is absent the
      endpoint degrades to a plan-only response; static hosting still plays canned scenarios.

Canned scenarios ($0 offline): explicitly requested via GET /api/run?mode=canned. Never the
default and never silently substituted for a fresh query.

Endpoints:
  GET  /api/health            -> {"live": bool, "model": str, "scenarios": [...],
                                  "subsystems": {"claude", "emet", "qmodels", "moat"}}
  GET  /api/run?q=<query>     -> the harnessed firm via live_engine.run_live (default; via=engine-live).
                                  ?mode=canned -> pre-captured scenario ($0 offline, via=canned);
                                  ?mode=claude -> headless-Claude reconstruction (via=claude-subscription).
                                  Output schema: contracts/run_live_schema.md (single source of truth).
  POST /api/chat              -> fresh engagement: in-process live_engine.run_live (via=engine-live);
                                  follow-up (dossier present, not a new target): grounded claude-p reply.
  GET  /  (and any path)      -> static files from ../site
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "site")

sys.path.insert(0, HERE)
from orchestrator import ENGINE, SCENARIOS  # noqa: E402
import live_engine  # noqa: E402  (the harnessed live firm — the real front door)

PORT = int(os.environ.get("SAPPHIRE_PORT", "8077"))
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")
CLAUDE_MODEL = os.environ.get("SAPPHIRE_MODEL", "")  # "" = subscription default (Opus)
CLAUDE_TIMEOUT = int(os.environ.get("SAPPHIRE_TIMEOUT", "240"))

# JSON schema for the LIVE portion Claude fills (the engine supplies the deterministic plan).
RUN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["headline", "discover", "validate", "consult", "synthesize"],
    "properties": {
        "headline": {"type": "string"},
        "discover": {
            "type": "object", "additionalProperties": False,
            "required": ["source", "summary", "result", "dossier", "flags", "status"],
            "properties": {
                "source": {"type": "string"}, "summary": {"type": "string"}, "result": {"type": "string"},
                "status": {"type": "string"},
                "dossier": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["field", "value", "source", "tier", "confidence"],
                    "properties": {"field": {"type": "string"}, "value": {"type": "string"},
                                   "source": {"type": "string"}, "tier": {"type": "string"},
                                   "confidence": {"type": "string"},
                                   "flag": {"type": "string", "enum": ["VETO", "DIVERGENCE", "KNOWN_UNKNOWN"]}}}},
                "flags": {"type": "object", "additionalProperties": False,
                          "required": ["VETO", "DIVERGENCE", "KNOWN_UNKNOWNS"],
                          "properties": {"VETO": {"type": "array", "items": {"type": "string"}},
                                         "DIVERGENCE": {"type": "array", "items": {"type": "string"}},
                                         "KNOWN_UNKNOWNS": {"type": "array", "items": {"type": "string"}}}},
            }},
        "validate": {
            "type": "object", "additionalProperties": False,
            "required": ["source", "runs", "result"],
            "properties": {"source": {"type": "string"}, "result": {"type": "string"},
                           "mock": {"type": "boolean"},
                           "runs": {"type": "array", "items": {
                               "type": "object", "additionalProperties": False,
                               "required": ["model", "out"],
                               "properties": {"model": {"type": "string"}, "out": {"type": "string"}}}}}},
        "consult": {
            "type": "object", "additionalProperties": False,
            "required": ["round1", "round2", "spread"],
            "properties": {
                "round1": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["persona", "role", "lens", "stance", "conviction", "headline", "rationale", "top_risk", "ask"],
                    "properties": {"persona": {"type": "string"}, "role": {"type": "string"},
                                   "lens": {"type": "string"}, "stance": {"type": "string"},
                                   "conviction": {"type": "integer"}, "headline": {"type": "string"},
                                   "rationale": {"type": "string"}, "top_risk": {"type": "string"}, "ask": {"type": "string"}}}},
                "round2": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["persona", "revised", "conviction", "shift"],
                    "properties": {"persona": {"type": "string"}, "revised": {"type": "boolean"},
                                   "conviction": {"type": "integer"}, "shift": {"type": "string"}}}},
                "spread": {"type": "object", "additionalProperties": False,
                           "required": ["consensus", "dissent", "convergent_gate", "conviction_range"],
                           "properties": {"consensus": {"type": "string"}, "dissent": {"type": "string"},
                                          "convergent_gate": {"type": "string"}, "conviction_range": {"type": "string"}}}}},
        "synthesize": {
            "type": "object", "additionalProperties": False,
            "required": ["recommendation", "consensus", "dissent", "convergent_gate", "proposed_experiment", "confidence"],
            "properties": {"recommendation": {"type": "string"}, "consensus": {"type": "string"},
                           "dissent": {"type": "string"}, "convergent_gate": {"type": "string"},
                           "proposed_experiment": {"type": "string"}, "confidence": {"type": "string"}}},
    },
}


# follow-up answer schema (grounded chat reply, no new run)
FOLLOWUP_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["text"],
    "properties": {"text": {"type": "string"}, "cites": {"type": "array", "items": {"type": "string"}}},
}

GENE_RE = re.compile(r"\b[A-Z][A-Z0-9]{2,}\b")
ENGAGEMENT_KW = ("prioriti", "rank", "triage", "fundable", "diligence", "trial", "go/no-go",
                 "portfolio", "franchise", "validate", "de-risk", "target list", "should we")


def _looks_like_engagement(msg: str) -> bool:
    """Fresh engagement (run the firm) vs follow-up (answer over the current dossier)."""
    m = msg.lower()
    if any(k in m for k in ENGAGEMENT_KW):
        return True
    if ENGINE.triage(msg)["disease"]:
        return True
    return bool(GENE_RE.search(msg))   # a gene-like token (SCN11A, RHEB, KCNQ2…) names a new target


def _provenance_for(source: str, origin: str) -> str:
    s = (source or "").lower()
    if any(k in s for k in ("mock", "q-models", "moat")):
        return "mock"
    if origin == "live":
        return "claude"          # web live runs never query EMET — facts are Claude's reconstruction
    return "emet" if "emet" in s else "other"


def _stamp(run: dict, origin: str) -> dict:
    """Tag every dossier fact with its true provenance; mark the run origin."""
    for f in run.get("discover", {}).get("dossier", []):
        f["provenance"] = _provenance_for(f.get("source", ""), origin)
    run["origin"] = origin       # 'captured' (shipped scenario) | 'live' (claude reconstruction)
    return run


def _follow_up(message: str, dossier: list, history: list) -> dict:
    """A grounded conversational reply over the CURRENT dossier — no new run."""
    ctx = "\n".join(f"- {f.get('field')}: {f.get('value')} [{f.get('source')}]" for f in (dossier or [])[:14])
    hist = "\n".join(f"{h.get('role')}: {h.get('content')}" for h in (history or [])[-6:])
    prompt = f"""You are the Sapphire Orchestrator answering a FOLLOW-UP in an ongoing conversation.
Answer ONLY from the current fact dossier below — these are the established facts; do not invent new
ones. If the dossier doesn't cover it, say so plainly and name the agent/tool that would have to run.
Concise (2–5 sentences). List the dossier fields you used in "cites".

CURRENT DOSSIER:
{ctx or '(no dossier yet — ask for a target prioritization first)'}

RECENT CONVERSATION:
{hist or '(none)'}

FOLLOW-UP: {message}"""
    cmd = [CLAUDE_BIN, "-p", prompt, "--output-format", "json", "--json-schema", json.dumps(FOLLOWUP_SCHEMA)]
    if CLAUDE_MODEL:
        cmd += ["--model", CLAUDE_MODEL]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT, cwd=ROOT)
        env = json.loads(proc.stdout)
        body = env.get("structured_output") or {"text": env.get("result", "")}
        model = (env.get("modelUsage") and list(env["modelUsage"].keys())[0]) or "claude (subscription)"
        return {"kind": "reply", "text": body.get("text", ""), "cites": body.get("cites", []), "live": True, "model": model}
    except Exception as e:
        return {"kind": "reply", "text": f"(Live brain unavailable: {type(e).__name__}. Start serve.py to enable follow-ups.)", "cites": [], "live": False}


def _prompt(query: str, plan: dict) -> str:
    panel = "; ".join(f"{s['lens']}: {s['persona']}" for s in plan["panel"])
    return f"""You are the Sapphire Orchestrator — Quiver Bioscience's CNS drug-discovery decision firm.
Run the full firm on this query and return ONLY the structured object (the schema is enforced).

QUERY: {query}

The engagement plan is already fixed (do not change it):
  deliverable: {plan['deliverable']}   disease: {plan['disease']}   modality: {plan['modality']}
  panel seated: {panel}; plus an Adversarial Red-Team.

Produce the four downstream stages, obeying these NON-NEGOTIABLE rules:
- Internal moat (Quiver EP/CRISPR latent space) AUTHORS the hypothesis — produce a ranked candidate with
  an internal rank; it is MOCK here (no real Quiver data) — say so in the relevant dossier field's source.
- EMET (external) only GATES (veto/demote) or BOOSTS (corroborate) — never authors. Mark a removed/
  contraindicated competitor as a VETO flag; mark a moat-vs-literature disagreement as DIVERGENCE
  (surface it, do not reconcile); mark thin/unproven items as KNOWN_UNKNOWN.
- Facts vs judgment: the dossier (discover) and Q-Models (validate) are CITED FACTS; the persona panel
  (consult) are OPINIONS that must reference the dossier — personas never invent facts.
- Q-Models (validate) are MOCK demo outputs (set "mock": true) shaped like Boltz-2 / ADMET-AI / CardioGenAI.
- Personas in round1 each give a verdict (stance: champion|conditional|skeptic|veto; conviction 1-5).
  In round2, each is shown the others and revises or holds with a reason. No forced consensus.
- If evidence is thin or contradictory, ABSTAIN in synthesis and propose the resolving experiment.
- HONESTY: you are NOT querying EMET or Q-Models live in this web run — the dossier facts are your own
  reconstruction from training. Do not claim a fact came from a live database hit; the UI labels these
  as Claude-reconstructed. Public identifiers only; never fabricate a PMID — cite a source TYPE
  (e.g. "EMET / GWAS Catalog") if you don't know the exact id. Keep every string concise (1–3 sentences)."""


def _run_live(query: str) -> dict:
    """Drive Claude Code headless on the user's subscription; merge with the engine plan."""
    plan = ENGINE.plan(query)
    plan_public = {k: v for k, v in plan.items() if not k.startswith("_")}
    cmd = [CLAUDE_BIN, "-p", _prompt(query, plan_public),
           "--output-format", "json", "--json-schema", json.dumps(RUN_SCHEMA)]
    if CLAUDE_MODEL:
        cmd += ["--model", CLAUDE_MODEL]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CLAUDE_TIMEOUT, cwd=ROOT)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return {"query": query, "plan": plan_public, "via": "plan", "live": False,
                "note": f"Live brain unavailable ({type(e).__name__}). Showing the plan; pick a scenario for a full run."}
    if proc.returncode != 0:
        return {"query": query, "plan": plan_public, "via": "plan", "live": False,
                "note": "Claude CLI returned an error. Showing the plan.", "stderr": proc.stderr[-400:]}
    try:
        env = json.loads(proc.stdout)
        body = env.get("structured_output") or json.loads(env["result"])
        model = (env.get("modelUsage") and list(env["modelUsage"].keys())[0]) or "claude (subscription)"
    except (json.JSONDecodeError, KeyError, IndexError):
        return {"query": query, "plan": plan_public, "via": "plan", "live": False,
                "note": "Could not parse the live response. Showing the plan."}
    run = {"id": "live", "title": f"Live run — {plan_public['disease']}", "query": query,
           "headline": body.get("headline", ""), "plan": plan_public,
           "discover": body["discover"], "validate": body["validate"],
           "consult": body["consult"], "synthesize": body["synthesize"],
           "via": "claude-subscription", "live": True, "model": model}
    return _stamp(run, "live")


def _run_engine_live(query: str, ctx: dict | None = None) -> dict:
    """Run the REAL harnessed firm (`live_engine.run_live`) and stamp the HTTP envelope.

    This is the live-firm service boundary K1 exposes — the integration point LOKA will call.
    `run_live` never raises for a down backend (the harness abstains honestly), so the result is
    always well-formed, possibly degraded. We still wrap in try/except so a *programming* error
    can never take down the endpoint; on that path we return an honest plan-only envelope.

    The returned dict is the documented `run_live` contract
    (`contracts/run_live_schema.md`) plus two HTTP stamps: `via="engine-live"`, `live=True`.
    """
    try:
        result = live_engine.run_live(query, ctx=ctx)
    except Exception as e:  # defensive — run_live is designed not to raise
        plan = ENGINE.plan(query)
        plan_public = {k: v for k, v in plan.items() if not k.startswith("_")}
        return {"query": query, "plan": plan_public, "via": "plan", "live": False,
                "note": f"engine-live unavailable ({type(e).__name__}: {str(e)[:160]})."}
    result["via"] = "engine-live"
    result["live"] = True
    return result


def _run_canned(query: str) -> dict:
    """The pre-captured-scenario path — an explicit, clearly-labeled $0 offline fallback.

    Routes the query to a shipped scenario by disease; if none matches, returns an honest note
    (so `?mode=canned` never silently degrades to a different path)."""
    from orchestrator import DISEASE_TO_SCENARIO
    sid = DISEASE_TO_SCENARIO.get(ENGINE.triage(query)["disease"])
    if sid:
        run = _stamp(ENGINE.run(sid), "captured")
        run.update({"via": "canned", "live": False, "_routed_from_query": query})
        return run
    plan = ENGINE.plan(query)
    plan_public = {k: v for k, v in plan.items() if not k.startswith("_")}
    return {"query": query, "plan": plan_public, "via": "canned", "live": False,
            "note": "No canned scenario matches this query; omit ?mode=canned for the live engine."}


def route_api_run(query: str, mode: str = "live") -> dict:
    """Pure routing decision for GET /api/run (testable without a live server).

    mode:
      "live"   (default) -> the harnessed firm via run_live           (via=engine-live)
      "canned"           -> a pre-captured scenario, $0 offline        (via=canned)
      "claude"           -> headless-Claude reconstruction (subscription) (via=claude-subscription)
    """
    if mode == "canned":
        return _run_canned(query)
    if mode == "claude":
        return _run_live(query)
    # "live" and any unrecognised mode fall through to the live firm (the safe,
    # forward-compatible default). Covered by test_unknown_mode_defaults_to_engine_live.
    return _run_engine_live(query)


def _qmodels_status() -> str:
    """Real Q-Models status for the systems panel: live-local (CPU endpoint serving real joblibs) /
    stub (endpoint up, placeholder) / mock (endpoint down)."""
    try:
        h = ENGINE._qmodels().health()
        if h.get("reachable"):
            return "live-local" if h.get("live_tracks") else "stub"
    except Exception:
        pass
    return "mock"


def _moat_status() -> str:
    """Real moat status: 'real' when the SQLite DB is present and has the neighbors table,
    'mock' otherwise (honest degrade — DB absent, symlink broken, or any error)."""
    try:
        from moat.client import MoatClient
        return "real" if MoatClient().available() else "mock"
    except Exception:
        return "mock"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=SITE, **k)

    def _json(self, obj, code=200):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            have = _claude_available()
            return self._json({"live": have, "model": CLAUDE_MODEL or "subscription default (Opus)",
                               "scenarios": list(SCENARIOS),
                               "subsystems": {"claude": "live" if have else "down",
                                              "emet": "not-wired", "qmodels": _qmodels_status(), "moat": _moat_status()}})
        if parsed.path == "/api/tools":
            return self._json({"tools": ENGINE.tools_catalog()})
        if parsed.path == "/api/run":
            qs = urllib.parse.parse_qs(parsed.query)
            q = qs.get("q", [""])[0].strip()
            if not q:
                return self._json({"error": "missing q"}, 400)
            # Default: the REAL harnessed firm (via=engine-live). The canned scenarios remain
            # reachable as an explicit $0 offline fallback via ?mode=canned; the headless-Claude
            # reconstruction via ?mode=claude.
            mode = qs.get("mode", ["live"])[0].strip().lower()
            return self._json(route_api_run(q, mode))
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/api/chat", "/api/tool"):
            return self._json({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length", "0") or 0)
        try:
            req = json.loads(self.rfile.read(length) or "{}")
        except json.JSONDecodeError:
            return self._json({"error": "bad json"}, 400)

        if parsed.path == "/api/tool":
            # the orchestrator calls any Q-Models model: {tool_id, inputs}
            tool_id = (req.get("tool_id") or "").strip()
            if not tool_id:
                return self._json({"error": "missing tool_id"}, 400)
            return self._json(ENGINE.call_model(tool_id, req.get("inputs") or {}))
        msg = (req.get("message") or "").strip()
        if not msg:
            return self._json({"error": "missing message"}, 400)
        history = req.get("history") or []
        dossier = req.get("current_dossier") or []

        # follow-up vs fresh engagement
        if dossier and not _looks_like_engagement(msg):
            return self._json(_follow_up(msg, dossier, history))

        # Fresh engagement: dispatch to the harnessed live firm (via=engine-live).
        # _run_engine_live never raises — it returns an honest plan-only envelope on any error.
        run = _run_engine_live(msg)
        return self._json({"kind": "run", "run": run,
                           "live": run.get("live", False),
                           "via": run.get("via", "engine-live")})

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("  " + (fmt % args) + "\n")


def _claude_available() -> bool:
    try:
        subprocess.run([CLAUDE_BIN, "--version"], capture_output=True, timeout=8)
        return True
    except Exception:
        return False


def main() -> int:
    live = _claude_available()
    print(f"Sapphire bridge → http://localhost:{PORT}")
    print(f"  site:   {SITE}")
    print(f"  live brain: {'YES — Claude Code on your subscription' if live else 'no (claude CLI not found) — canned scenarios only'}")
    print(f"  scenarios (instant): {', '.join(SCENARIOS)}")
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
