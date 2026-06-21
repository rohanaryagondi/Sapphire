"""The tiered governance switch (spec §6.5). Default: memory auto-applies; behavior-change
(skills/specs/scenarios/routes) is gated to the proposed/ queue for human approval. Moving to
fully-autonomous later = flip these flags — no code change."""
from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parent / "governance.json"


def load_policy(path=None) -> dict:
    p = Path(path) if path else Path(os.environ.get("SAPPHIRE_GOVERNANCE", str(_DEFAULT)))
    return json.loads(p.read_text(encoding="utf-8"))


def may_auto_apply(artifact_type: str, policy=None) -> bool:
    pol = policy if policy is not None else load_policy()
    return bool(pol.get("auto_apply", {}).get(artifact_type, False))


def trigger_count(policy=None) -> int:
    pol = policy if policy is not None else load_policy()
    return int(pol.get("authoring_trigger_count", 3))


def freshness_days(policy=None) -> int:
    pol = policy if policy is not None else load_policy()
    return int(pol.get("freshness_days", 90))
