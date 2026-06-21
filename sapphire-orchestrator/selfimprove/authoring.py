"""Tier-2 gated authoring (spec §6.4): draft new behavior (skills/specs/scenarios/routes)
into the proposed/ review queue. Nothing is applied unless governance allows it (the tiered
default gates all behavior-change for human approval)."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .governance import load_policy, may_auto_apply, trigger_count

_DEFAULT_PROPOSED = Path(__file__).resolve().parents[1] / "proposed"


def _dir() -> Path:
    d = Path(os.environ.get("SAPPHIRE_PROPOSED_DIR", str(_DEFAULT_PROPOSED)))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_-]+", "-", s.lower()).strip("-") or "item"


def propose(artifact_type: str, name: str, content: str, rationale: str, policy=None) -> dict:
    pol = policy if policy is not None else load_policy()
    proposal = {
        "artifact_type": artifact_type, "name": name, "content": content,
        "rationale": rationale, "auto_applied": may_auto_apply(artifact_type, pol),
    }
    (_dir() / f"{artifact_type}-{_slug(name)}.json").write_text(
        json.dumps(proposal, indent=2), encoding="utf-8")
    return proposal


def propose_from_routes(route_counts: dict, policy=None) -> list:
    pol = policy if policy is not None else load_policy()
    threshold = trigger_count(pol)
    out = []
    for route, count in route_counts.items():
        if count >= threshold:
            out.append(propose("scenarios", route,
                               f"# TODO: capture a scenario for route '{route}'",
                               f"seen {count}x with no scenario", pol))
    return out
