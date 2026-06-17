#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sapphire bridge — serves the site AND runs the orchestrator LIVE under your Claude subscription.

    python sapphire-orchestrator/serve.py            # http://localhost:8077  (Console = main site)

How "Claude under the hood" works here:
  - Shipped scenarios (or a query that routes to one) are answered instantly by the deterministic
    engine (orchestrator.py) — $0, no model call.
  - A NOVEL query is handed to Claude Code headless (`claude -p ... --json-schema`), which runs on
    your **subscription** (no API key). Claude acts as the whole firm and returns a structured run;
    the engine still computes the engagement PLAN deterministically, so the plan is stable and only
    the facts/verdicts are model-generated.
  - If the `claude` CLI is missing or errors, the endpoint degrades to a plan-only response, and the
    static Console (served by any web server) still plays the canned scenarios. So it works anywhere;
    the bridge just adds the live brain.

Endpoints:
  GET /api/health            -> {"live": bool, "model": str, "scenarios": [...]}
  GET /api/run?q=<query>     -> canonical run object (+ "via": engine|claude-subscription|plan)
  GET /  (and any path)      -> static files from ../site
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SITE = os.path.join(ROOT, "site")

sys.path.insert(0, HERE)
from orchestrator import ENGINE, SCENARIOS  # noqa: E402

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
- Public identifiers only; never fabricate a PMID — cite a source type (e.g. "EMET / GWAS Catalog") if
  you don't know the exact id. Keep every string concise (one to three sentences)."""


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
    return run


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
                               "scenarios": list(SCENARIOS)})
        if parsed.path == "/api/run":
            q = urllib.parse.parse_qs(parsed.query).get("q", [""])[0].strip()
            if not q:
                return self._json({"error": "missing q"}, 400)
            tri = ENGINE.triage(q)
            from orchestrator import DISEASE_TO_SCENARIO
            sid = DISEASE_TO_SCENARIO.get(tri["disease"])
            if sid:
                run = ENGINE.run(sid)
                run.update({"via": "engine", "live": False, "_routed_from_query": q})
                return self._json(run)
            return self._json(_run_live(q))
        return super().do_GET()

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
