"""Core harness types + input hashing (spec §A.2/§A.3)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


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
    # When True, this claude-subagent does REAL reasoning even under SAPPHIRE_SIMULATE_MODELS=1
    # (it is NOT replaced by the 🧪 simulated stub). Reserved for the scientific-core reasoners
    # whose output IS the deliverable (e.g. rescue-mechanism) — so a fast demo can stub the
    # personas/semantic agents while the science still runs for real. Tests still inject a mock
    # runner via ctx so an exempt agent never shells a real `claude -p` in CI.
    simulate_exempt: bool = False


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


_REG_PATH = Path(__file__).resolve().parent / "agents.json"


def load_registry(path=None) -> dict:
    p = Path(path) if path else _REG_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def _inline_ref(node, registry):
    """Resolve a top-level {'$ref': '#/schemas/X'} to its concrete (self-contained) schema dict."""
    if isinstance(node, dict) and set(node.keys()) == {"$ref"}:
        ref = node["$ref"]
        if not ref.startswith("#/"):
            raise ValueError(f"unsupported $ref {ref!r}")
        cur = registry
        for part in ref[2:].split("/"):
            cur = cur[part]
        return cur
    return node


def resolve(agent_id: str, registry=None) -> Contract:
    reg = registry if registry is not None else load_registry()
    entry = next((a for a in reg.get("agents", []) if a["id"] == agent_id), None)
    if entry is None:
        raise KeyError(agent_id)
    retry = entry.get("retry", {})
    return Contract(
        id=entry["id"],
        role=entry.get("role", ""),
        kind=entry["kind"],
        spec=entry.get("spec"),
        input_schema=_inline_ref(entry.get("input_schema"), reg),
        output_schema=_inline_ref(entry.get("output_schema"), reg),
        tools_allowed=list(entry.get("tools_allowed", [])),
        guardrails=list(entry.get("guardrails", [])),
        provenance_label=entry.get("provenance_label", "synthesis"),
        timeout_s=entry.get("timeout_s", 120),
        max_repair=retry.get("max_repair", 2),
        on_hard_fail=retry.get("on_hard_fail", "abstain"),
        veto_class=entry.get("veto_class", False),
        param=entry.get("param"),
        simulate_exempt=entry.get("simulate_exempt", False),
    )
