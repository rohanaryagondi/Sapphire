"""Capture the REAL TSC2 run_live via the SESSION-BRIDGE as a $0 deterministic replay scenario.

The front end's real-EMET path: the captured EMET envelope (driven live in the orchestrator's
authenticated BenchSci session, chat c4a1031a — 9 real TSC2 PMIDs) is auto-loaded from
scenarios/emet_envelopes/tsc2.json and injected via make_session_emet_handler. Real moat + the
9 real EMET PMIDs + the roundtable spread + synthesis are frozen.

Persona mode is controlled by SAPPHIRE_SIMULATE_MODELS:
  - unset (DEFAULT here): REAL haiku personas → a REAL spread (preferred; slower).
  - "1": 🧪 simulated personas (labeled) → fast, for when real personas are too slow/flaky.

Writes sapphire-orchestrator/scenarios/tsc2_emet_session.json (internal-only tagged: real moat).
Re-runnable: a fresh run reproduces the committed JSON (modulo model nondeterminism in the spread).
"""
import os, sys, json, time, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.path.join(ROOT, "sapphire-orchestrator")
sys.path.insert(0, ENG)
os.environ.setdefault("SAPPHIRE_ENGAGEMENTS_DIR", tempfile.mkdtemp())
os.environ.setdefault("SAPPHIRE_MEMORY_DIR", tempfile.mkdtemp())
os.environ.setdefault("CLAUDE_MODEL", "claude-haiku-4-5")

from emet.envelopes import load_envelope_for
from emet.session_bridge import make_session_emet_handler
from live_engine import run_live

CAND = "TSC2"
QUERY = "Is TSC2 a viable target in tuberous sclerosis?"
env = load_envelope_for(CAND)
assert env, "no captured envelope for TSC2 — expected scenarios/emet_envelopes/tsc2.json"
n_pmids = len(env.get("evidence", []))

# The front-end real-EMET path: the in-session handler backed by the captured envelope.
ctx = {"emet_handler": make_session_emet_handler({CAND: env})}
simulated = os.environ.get("SAPPHIRE_SIMULATE_MODELS") == "1"
persona_mode = "simulated" if simulated else "haiku"

t0 = time.monotonic()
result = run_live(QUERY, ctx=ctx)
wall = round(time.monotonic() - t0, 1)

# Stamp scenario metadata FROM THE TOOL (reproducible; no manual edit).
result["_captured_at"] = "2026-06-25"
result["_wall_s"] = wall
result["_scenario"] = "tsc2_emet_session"
result["_via"] = "replay-capture"
result["_persona_mode"] = persona_mode
result["_emet_session"] = [CAND]
result["_internal_only"] = True
result["_data_notice"] = (
    "Contains REAL internal Quiver moat data (provenance=moat-real, plane=internal). Approved for "
    "INTERNAL demo only — do NOT distribute externally. EMET facts are real public PMIDs (external "
    "plane), captured live in the orchestrator's authenticated BenchSci session (chat c4a1031a) and "
    "injected via the session-bridge (emet/session_bridge.py). Personas: " + persona_mode + ". "
    "Captured via _build/capture_tsc2_emet_session.py."
)
out = os.path.join(ENG, "scenarios", "tsc2_emet_session.json")
json.dump(result, open(out, "w"), indent=2)

import collections, re
d = result["discover"]
emet = [f for f in d["dossier"] if f.get("provenance") == "emet-live"]
pmids = sorted({m for f in emet for m in re.findall(r"PMID:\d+", f.get("source", ""))})
print("WALL", wall, "s | personas:", persona_mode)
print("dossier", len(d["dossier"]), "provenances",
      dict(collections.Counter(f.get("provenance") for f in d["dossier"])))
print("EMET-live PMIDs:", len(pmids), pmids)
print("flags", {k: len(v) for k, v in d["flags"].items()})
round1 = result["consult"]["round1"]
print("round1 personas", len(round1), "stances", [v.get("stance") for v in round1])
print("synthesis:", result["synthesize"]["recommendation"][:90])
print("wrote", out)
