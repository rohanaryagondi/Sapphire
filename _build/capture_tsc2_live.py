"""Capture the REAL TSC2 run_live as a deterministic scenario for $0 front-end replay.
Real moat + REAL EMET (live-captured envelope injected via make_emet_handler) + haiku firm.
Writes sapphire-orchestrator/scenarios/tsc2_live_run.json (the real run, internal-only tagged).
"""
import os, sys, json, time, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENG = os.path.join(ROOT, "sapphire-orchestrator")
sys.path.insert(0, ENG); sys.path.insert(0, os.path.join(ENG, "tests"))
os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = tempfile.mkdtemp()
os.environ["SAPPHIRE_MEMORY_DIR"] = tempfile.mkdtemp()
os.environ["CLAUDE_MODEL"] = "claude-haiku-4-5"

ENVELOPE = json.load(open(os.environ["TSC2_ENVELOPE_JSON"]))
from emet.handler import make_emet_handler
from live_engine import run_live

# Inject the live-captured EMET envelope (real PMIDs) + let moat/personas/fact-agents run real (haiku).
ctx = {"emet_handler": make_emet_handler(runner=lambda inputs: ENVELOPE)}
t0 = time.monotonic()
result = run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx=ctx)
result["_captured_at"] = "2026-06-25"
result["_wall_s"] = round(time.monotonic() - t0, 1)
# Stamp the scenario metadata from the TOOL (not a manual edit) so a re-run reproduces the
# committed JSON — including the internal-only safeguard.
result["_scenario"] = "tsc2_live_run"
result["_via"] = "replay-capture"
result["_internal_only"] = True
result["_data_notice"] = (
    "Contains REAL internal Quiver moat data (provenance=moat-real, plane=internal). Approved for "
    "INTERNAL demo only — do NOT distribute externally. EMET facts are real public PMIDs (external "
    "plane). Captured via _build/capture_tsc2_live.py (real moat + live-captured EMET envelope + "
    "haiku firm)."
)
out = os.path.join(ENG, "scenarios", "tsc2_live_run.json")
json.dump(result, open(out, "w"), indent=2)
d = result["discover"]
import collections
print("WALL", result["_wall_s"], "s")
print("dossier", len(d["dossier"]), "provenances", dict(collections.Counter(f.get("provenance") for f in d["dossier"])))
print("flags", d["flags"])
print("round1 personas", len(result["consult"]["round1"]))
print("wrote", out)
