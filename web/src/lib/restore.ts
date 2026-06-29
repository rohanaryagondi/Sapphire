/* ============================================================================
   Restore helpers — rebuild a fully-rendered Turn from a PERSISTED run.

   The live SSE progress stream is NOT stored (only the final run_live result dict
   is). When a conversation is reopened from history, we synthesise a STATIC trace
   from `result.discover.agents` + plan + flags + roundtable + synthesis so the
   Monitor (which folds `turn.trace` via buildTrace) and Investigate still render the
   final agent roster + statuses on a restored chat — identical in shape to a live run,
   just with every node already `phase:"done"`. Nothing is fabricated: every field is
   read straight off the stored result.
   ============================================================================ */
import type { AgentStatus, ProgressEvent, RunResult } from "./types";
import { finalVerdicts } from "./verdicts";

/** This agent's REAL fact count, restored honestly:
 *   1. prefer the engine-persisted `n_facts` (authoritative);
 *   2. else attribute by provenance ONLY when that provenance is unique to one
 *      agent (a safe 1:1 map);
 *   3. else `undefined` — multiple agents share the provenance, so we cannot
 *      attribute a per-agent count and must NOT fabricate one (the old code
 *      assigned the full shared count to every sharing agent, e.g. the moat's
 *      12 facts showed on every row). */
function factsForAgent(
  result: RunResult,
  agent: AgentStatus,
  provAgentCount: Map<string, number>,
): number | undefined {
  if (typeof agent.n_facts === "number") return agent.n_facts;
  const prov = agent.provenance;
  if (prov && provAgentCount.get(prov) === 1) {
    return (result.discover?.dossier ?? []).filter((f) => f.provenance === prov).length;
  }
  return undefined;
}

/** Synthesise the static progress trace for a completed run. Returns [] for an
 *  empty/degraded result so the Monitor falls back to its empty state. */
export function traceFromResult(result?: RunResult | null): ProgressEvent[] {
  if (!result) return [];
  const events: ProgressEvent[] = [];

  // 1. plan
  const plan = result.plan;
  if (plan) {
    events.push({
      stage: "plan",
      phase: "done",
      deliverable: plan.deliverable,
      disease: plan.disease,
      modality: plan.modality,
      agents: plan.agents ?? [],
      panel: plan.panel ?? [],
    });
  }

  // 2. bucket1 — one done node per fact agent that ran. Each row shows ITS OWN
  //    fact count (persisted n_facts, or a safe unique-provenance fallback).
  const agents = result.discover?.agents ?? [];
  const provAgentCount = new Map<string, number>();
  for (const a of agents) {
    provAgentCount.set(a.provenance, (provAgentCount.get(a.provenance) ?? 0) + 1);
  }
  for (const a of agents) {
    events.push({
      stage: "bucket1",
      phase: "done",
      agent_id: a.id,
      status: a.status,
      provenance: a.provenance,
      n_facts: factsForAgent(result, a, provAgentCount),
    });
  }

  // 3. flags
  const flags = result.discover?.flags;
  if (flags) {
    events.push({
      stage: "flags",
      phase: "done",
      n_veto: (flags.VETO ?? []).length,
      n_divergence: (flags.DIVERGENCE ?? []).length,
      n_known_unknowns: (flags.KNOWN_UNKNOWNS ?? []).length,
    });
  }

  // 4. roundtable — the SAME normalised verdicts the spread renders (round-2
  //    deltas merged over round-1), so the Monitor never contradicts the spread.
  for (const v of finalVerdicts(result)) {
    events.push({
      stage: "roundtable",
      phase: "done",
      agent_id: v.persona,
      status: v.status,
      stance: v.stance,
      conviction: v.conviction,
      provenance: v.provenance,
    });
  }

  // 5. synthesis
  const s = result.synthesize;
  if (s) {
    events.push({
      stage: "synthesis",
      phase: "done",
      recommendation: s.recommendation,
      confidence: s.confidence,
    });
  }

  return events;
}
