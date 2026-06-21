"""Repeatable scenario capture (spec §5): assemble a DRAFT scenario from the planner + a live
EMET pass + Q-Models, for human curation. Injectable sources so it is offline-testable; the live
wiring lives in _build/capture_scenario.py. Drafts are clearly marked unfinished — never a
fabricated final scenario."""
from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULT_DRAFTS = Path(__file__).resolve().parent / "scenarios" / "drafts"


def _drafts_dir() -> Path:
    d = Path(os.environ.get("SAPPHIRE_DRAFTS_DIR", str(_DEFAULT_DRAFTS)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def draft_scenario(query, *, plan_fn, emet_fn=None, qmodels_fn=None) -> dict:
    plan = plan_fn(query)
    findings = emet_fn(query) if emet_fn else {"candidate": "", "facts": []}
    runs = qmodels_fn(query) if qmodels_fn else []
    dossier = [{"field": "?", "value": f["value"], "source": f["source"],
                "tier": f.get("tier", "T2"), **({"flag": f["flag"]} if f.get("flag") else {})}
               for f in findings.get("facts", [])]
    return {
        "id": plan["id"], "title": plan["title"], "query": query,
        "headline": plan.get("headline", ""),
        "discover": {"source": "EMET (live) + internal moat (mock)", "dossier": dossier,
                     "flags": {"VETO": [], "DIVERGENCE": [], "KNOWN_UNKNOWNS": []}, "status": "draft"},
        "validate": {"source": "Q-Models", "runs": runs, "mock": False},
        "panel": [], "rebuttal": [],
        "synthesize": {"recommendation": "", "confidence": "", "proposed_experiment": ""},
        "_status": "draft",
        "_todo": "human curation: tier/cite facts, seat panel, write synthesis; then drop _status and move to scenarios/",
    }


def write_draft(draft) -> Path:
    p = _drafts_dir() / f"{draft['id']}.json"
    p.write_text(json.dumps(draft, indent=2), encoding="utf-8")
    return p
