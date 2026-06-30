import type { ProgressEvent } from "@/lib/types";

export interface TraceNode {
  started: boolean;
  done: boolean;
  ev: ProgressEvent;
}

export interface TraceRow extends TraceNode {
  agentId: string;
}

export interface TraceModel {
  plan?: TraceNode;
  bucket1: TraceRow[];
  flags?: TraceNode;
  roundtable: TraceRow[];
  synthesis?: TraceNode;
  /** total agents seen in bucket1 + how many finished */
  b1Done: number;
  rtDone: number;
}

const TOP = new Set(["plan", "flags", "synthesis"]);

/** Fold the streamed progress events into an ordered, in-place-updatable model. */
export function buildTrace(trace: ProgressEvent[]): TraceModel {
  const tops: Record<string, TraceNode> = {};
  const b1 = new Map<string, TraceRow>();
  const rt = new Map<string, TraceRow>();

  for (const ev of trace) {
    const stage = String(ev.stage ?? "");
    const phase = String(ev.phase ?? "");
    if (TOP.has(stage)) {
      const node = tops[stage] ?? { started: false, done: false, ev };
      node.started = true;
      node.ev = { ...node.ev, ...ev };
      if (phase === "done") node.done = true;
      tops[stage] = node;
      continue;
    }
    if (stage === "bucket1" || stage === "redispatch" || stage === "roundtable") {
      // "redispatch" is treated as bucket1 (re-dispatch of a bucket1 agent after a gap)
      const map = stage === "roundtable" ? rt : b1;
      const id = String(ev.agent_id ?? "");
      const row = map.get(id) ?? { agentId: id, started: false, done: false, ev };
      row.started = true;
      row.ev = { ...row.ev, ...ev };
      // phase==="rebuttal_done" is the round-2 terminal phase; treat it as done
      if (phase === "done" || phase === "rebuttal_done") row.done = true;
      map.set(id, row);
    }
  }

  const bucket1 = [...b1.values()];
  const roundtable = [...rt.values()];
  return {
    plan: tops.plan,
    bucket1,
    flags: tops.flags,
    roundtable,
    synthesis: tops.synthesis,
    b1Done: bucket1.filter((r) => r.done).length,
    rtDone: roundtable.filter((r) => r.done).length,
  };
}
