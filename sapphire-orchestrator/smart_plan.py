"""smart_plan.py — LLM-assisted Bucket-1 agent selection for Sapphire.

Provides ``smart_plan()`` which calls the LLM (via dispatch_claude) to select
a subset of the Bucket-1 agents most relevant to a given query, reducing the
panel and focusing compute on what matters.

Runtime stays stdlib-only: only stdlib and first-party imports appear here.
"""
from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from harness.contracts import Contract
from harness.dispatch import dispatch_claude


class SmartPlanError(ValueError):
    """Raised when smart_plan cannot produce a valid structured agent selection.

    Two causes:
      - hallucinated agent id (LLM returned an id not in the candidate universe)
      - unparseable JSON (LLM output or runner stdout could not be parsed)
    """
    pass


# ---------------------------------------------------------------------------
# JSON schema for the LLM's structured output
# ---------------------------------------------------------------------------
_SMART_PLAN_SCHEMA: dict = {
    "type": "object",
    "required": ["selected_agents", "dropped_agents", "panel_rationale", "notes"],
    "properties": {
        "selected_agents": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "why"],
                "properties": {
                    "id": {"type": "string"},
                    "why": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "dropped_agents": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "why"],
                "properties": {
                    "id": {"type": "string"},
                    "why": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        "panel_rationale": {"type": "string"},
        "notes": {"type": "string"},
    },
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# Synthetic Contract for the smart-plan LLM call.
#
# simulate_exempt=True: even under SAPPHIRE_SIMULATE_MODELS=1 the real runner
# is invoked (tests inject a mock runner via ctx["runner"]; gate-5 tests rely
# on this so the fake_runner controls which agents are "selected"). Without
# simulate_exempt, _simulate_claude would return selected_agents=[] and the
# gate-5 assertion that emet-runner ran would fail.
# ---------------------------------------------------------------------------
_SMART_PLAN_CONTRACT = Contract(
    id="smart-plan",
    role="planning",
    kind="claude-subagent",
    spec=None,
    output_schema=_SMART_PLAN_SCHEMA,
    tools_allowed=[],
    timeout_s=90,
    simulate_exempt=True,
)


def smart_plan(query: str, deterministic_plan: dict, registry: dict, ctx: dict) -> dict:
    """Use an LLM to select which Bucket-1 agents should run for this query.

    Parameters
    ----------
    query              : the free-text engagement question.
    deterministic_plan : the plan dict from ``Orchestrator.plan(query)``.
    registry           : the loaded agents.json dict (passed in so this function
                         stays side-effect-free and easily testable).
    ctx                : harness context dict; must carry a ``"runner"`` key —
                         the mock-injectable subprocess runner from
                         ``harness/dispatch.py`` (see dispatch_claude).

    Returns
    -------
    A dict with keys: ``selected_agents``, ``dropped_agents``,
    ``panel_rationale``, ``notes``.  Callers add ``plan_source`` themselves.

    Raises
    ------
    SmartPlanError
        - On a hallucinated agent id (id not in the candidate universe):
          ``"hallucinated agent id: '<id>'"``
        - On any JSON parse failure:
          ``"unparseable JSON from smart_plan"``

    Notes
    -----
    The plan rationale is metadata, NOT a cited fact — it carries no provenance
    label from ``contracts/provenance.py``.  Public identifiers only are sent to
    the model (agent IDs, roles, deterministic plan metadata).
    """
    # Import here to avoid a circular import at module level:
    # smart_plan ← live_engine ← smart_plan would be a cycle.
    from live_engine import _BUCKET1_AGENTS

    # Candidate universe = _BUCKET1_AGENTS ∩ ids present in the registry.
    known_ids = {a["id"] for a in registry.get("agents", [])}
    universe = [aid for aid in _BUCKET1_AGENTS if aid in known_ids]
    universe_set = set(universe)

    # Build role descriptions for each agent in the universe.
    # Public identifiers only — agent IDs and declared roles, never internal data.
    agent_entries = {a["id"]: a for a in registry.get("agents", [])}
    agent_descriptions = [
        {"id": aid, "role": agent_entries.get(aid, {}).get("role", "")}
        for aid in universe
    ]

    # Inputs for the LLM call — public identifiers only; no Quiver internal data.
    inputs = {
        "query": query,
        "universe": agent_descriptions,
        "deterministic_plan": {k: v for k, v in deterministic_plan.items()
                               if not k.startswith("_")},
        "instruction": (
            "You are the Sapphire planning agent. Select which Bucket-1 agents from the "
            "universe below should run for this query. Include in selected_agents those "
            "that are most relevant to the query's disease/modality/question; drop the rest "
            "with a brief reason. Return ALL agents in either selected_agents or "
            "dropped_agents. Public identifiers only — no Quiver internal data."
        ),
    }

    # Dispatch to the LLM via dispatch_claude.
    # The contract has simulate_exempt=True so that SAPPHIRE_SIMULATE_MODELS=1
    # still calls the injected runner (needed for gate-5 and offline CI tests).
    try:
        result = dispatch_claude(_SMART_PLAN_CONTRACT, inputs,
                                 runner=ctx.get("runner"))
    except json.JSONDecodeError:
        raise SmartPlanError("unparseable JSON from smart_plan")
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise SmartPlanError("unparseable JSON from smart_plan") from exc

    if result is None or not isinstance(result, dict):
        raise SmartPlanError("unparseable JSON from smart_plan")

    # Validate: every id in selected_agents must be in the candidate universe.
    # Hallucinated ids are a hard error — callers must not run an agent that
    # doesn't exist in the registry.
    for entry in result.get("selected_agents", []):
        bad_id = entry.get("id")
        if bad_id not in universe_set:
            raise SmartPlanError(f"hallucinated agent id: {bad_id!r}")

    return result
