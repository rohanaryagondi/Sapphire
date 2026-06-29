/* ============================================================================
   finalVerdicts — the SINGLE source of truth for the partner roundtable spread.

   The engine emits round-2 entries as rebuttal DELTAS: `{persona, conviction,
   revised, shift}` — they deliberately omit `stance` / `status` / `provenance`
   (those didn't change unless `revised`). Rendering a bare round-2 entry on its
   own makes a deliberating partner look "abstained" (no status === "ok"), which
   contradicted the Monitor (which folded the richer round-1 trace). This helper
   merges each round-2 delta over its round-1 verdict by persona, so the Spread,
   the Monitor and Investigate all render ONE coherent, honest final verdict:
   round-1's stance/status/provenance + round-2's updated conviction/rationale.

   Nothing is fabricated: a partner that genuinely abstained in round 1 (status
   !== "ok") stays abstained; we only restore the fields round 2 omitted.
   ============================================================================ */
import type { RunResult, Verdict } from "./types";

export function finalVerdicts(result?: RunResult | null): Verdict[] {
  const consult = result?.consult;
  if (!consult) return [];
  const round1 = consult.round1 ?? [];
  const round2 = consult.round2 ?? [];
  if (!round2.length) return round1;

  const r1ByPersona = new Map(round1.map((v) => [v.persona, v]));
  return round2.map((r2) => {
    const r1 = r1ByPersona.get(r2.persona);
    if (!r1) return r2; // no round-1 match — render the delta as-is
    return {
      ...r1,
      ...r2,
      // round 2 omits these — keep round 1's unless round 2 actually carries them
      stance: r2.stance ?? r1.stance,
      status: r2.status ?? r1.status,
      provenance: r2.provenance ?? r1.provenance,
      lens: r2.lens ?? r1.lens,
      conviction: r2.conviction ?? r1.conviction,
      // prefer round-2's rebuttal note (`shift`) as the rationale when present
      rationale: r2.shift || r2.rationale || r1.rationale,
    };
  });
}

/** True when this run's spread reflects a completed round-2 rebuttal. */
export function isRebuttalRound(result?: RunResult | null): boolean {
  return !!result?.consult?.round2?.length;
}
