"""Core harness types + input hashing (spec §A.2/§A.3)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field


@dataclass
class Contract:
    id: str
    role: str
    kind: str                       # python | qmodels-delegate | claude-subagent | emet-playwright
    spec: str | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    tools_allowed: list = field(default_factory=list)
    guardrails: list = field(default_factory=list)
    provenance_label: str = "synthesis"
    timeout_s: int = 120
    max_repair: int = 2
    on_hard_fail: str = "abstain"    # abstain | escalate
    veto_class: bool = False
    param: str | None = None


@dataclass
class AgentResult:
    agent_id: str
    ok: bool
    output: dict
    provenance: str
    status: str                      # ok | abstained | escalated
    error: str | None = None
    meta: dict = field(default_factory=dict)


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def inputs_hash(agent_id: str, inputs) -> str:
    digest = hashlib.sha256((agent_id + "\n" + canonical_json(inputs)).encode("utf-8")).hexdigest()
    return "sha256:" + digest
