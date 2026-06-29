/* ============================================================================
   Citation model — the Perplexity-defining layer.

   The run_live result carries a cited fact dossier (Fact[]) but no separate
   "sources" array and no inline citation markers in the synthesis prose. We
   derive citations *honestly* from the dossier itself: every dossier fact is a
   numbered source [n] (1-based, in dossier order). Fact cards, the answer
   prose, persona verdicts, and the bottom source grid all reference the SAME
   numbers — so a number always resolves to a real fact with real provenance.
   Nothing is fabricated; we only number what the engine already emitted.
   ============================================================================ */
import type { Fact, RunResult } from "./types";

export interface Source {
  /** 1-based citation number, stable across the whole answer */
  num: number;
  /** index into result.discover.dossier */
  index: number;
  fact: Fact;
  internal: boolean;
}

export function buildSources(result?: RunResult): Source[] {
  const dossier = result?.discover?.dossier ?? [];
  return dossier.map((fact, index) => ({
    num: index + 1,
    index,
    fact,
    internal: fact.plane === "internal",
  }));
}

/** A short, human label for the source (journal / source string / field). */
export function sourceTitle(fact: Fact): string {
  return fact.field || fact.source || fact.value.slice(0, 64) || "source";
}

/** The provenance/source line shown under a source title. */
export function sourceMeta(fact: Fact): string {
  const bits = [fact.source, fact.provenance].filter(Boolean) as string[];
  return bits.join(" · ");
}

/** Smooth-scroll to a source card and flash it (Perplexity citation jump). */
export function jumpToSource(turnId: string, num: number) {
  if (typeof document === "undefined") return;
  const el = document.getElementById(`src-${turnId}-${num}`);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.remove("cite-flash");
  // force reflow so the animation can replay
  void el.offsetWidth;
  el.classList.add("cite-flash");
}
