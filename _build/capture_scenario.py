"""Live scenario capture CLI: python _build/capture_scenario.py "<query>"
Drives the real planner + emet-runner (needs a logged-in BenchSci session) + Q-Models,
and writes a DRAFT to scenarios/drafts/ for human curation. Never writes a final scenario."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sapphire-orchestrator"))

from capture import draft_scenario, write_draft       # noqa: E402
from orchestrator import Orchestrator                 # noqa: E402
from emet.handler import make_emet_handler            # noqa: E402
from harness.contracts import resolve                 # noqa: E402


def _plan_fn(query):
    eng = Orchestrator()
    tri = eng.triage(query)
    return {"id": (tri.get("disease") or "new_scenario"), "title": tri.get("disease_label", "New scenario"),
            "headline": "", "query": query}


def _emet_fn(query):
    handler = make_emet_handler()                      # live Playwright runner
    return handler(resolve("emet-runner"), {"candidate": query, "question": query})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('usage: python _build/capture_scenario.py "<query>"'); sys.exit(2)
    q = sys.argv[1]
    draft = draft_scenario(q, plan_fn=_plan_fn, emet_fn=_emet_fn)
    path = write_draft(draft)
    print(f"draft written: {path} (curate it, then move to scenarios/)")
