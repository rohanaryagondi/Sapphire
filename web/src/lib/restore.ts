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
import type { ProgressEvent, RunResult } from "./types";

/** Count dossier facts attributable to an agent by shared provenance (best-effort —
 *  the engine doesn't persist a per-agent fact count, so we derive it the same way
 *  Investigate's AgentDetail does). */
function factsForProvenance(result: RunResult, prov?: string): number {
  if (!prov) return 0;
  return (result.discover?.dossier ?? []).filter((f) => f.provenance === prov).length;
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

  // 2. bucket1 — one done node per fact agent that ran
  for (const a of result.discover?.agents ?? []) {
    events.push({
      stage: "bucket1",
      phase: "done",
      agent_id: a.id,
      status: a.status,
      provenance: a.provenance,
      n_facts: factsForProvenance(result, a.provenance),
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

  // 4. roundtable — prefer the final (round2) verdicts; else round1
  const consult = result.consult;
  const round = consult?.round2?.length ? consult.round2 : (consult?.round1 ?? []);
  for (const v of round) {
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
