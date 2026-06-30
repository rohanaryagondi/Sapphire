// export-synthesis.ts
// Synthesis -> faithful cited Markdown (clipboard + download).
// Rule: never fabricate -- only what's in the result. Unknowns stay flagged.
import type { RunResult } from "./types";
import { finalVerdicts, isRebuttalRound } from "./verdicts";

interface RankedCandidate {
  rank?: number;
  gene?: string;
  reasoning?: string;
  source?: string;
  excluded?: boolean;
}

/** Build the cited Markdown string from a RunResult. Pure -- no side effects. */
export function buildSynthesisMarkdown(result: RunResult): string {
  const s = result.synthesize;
  const parts: string[] = [];

  // Prefer the Claude-synthesized narrative report when present.
  if (s?.report) {
    const header = `# Sapphire Analysis: ${result.query || result.engagement_id || ""}\n\n_Exported ${new Date().toISOString()}_\n\n`;
    const footer = `\n\n---\n_Sapphire -- Quiver Bioscience CNS drug-discovery firm_\n_Engine: run_live | Provenance preserved | No facts fabricated_\n`;
    return header + s.report + footer;
  }

  const query = result.query || result.engagement_id || "";
  parts.push(`# Sapphire Analysis: ${query}`);
  parts.push("");
  parts.push(`_Exported ${new Date().toISOString()}_`);
  parts.push("");

  // Recommendation
  if (s?.recommendation) {
    parts.push("## Recommendation");
    parts.push("");
    parts.push(s.recommendation);
    parts.push("");
    if (s.confidence) {
      parts.push(`**Confidence:** ${s.confidence}`);
      parts.push("");
    }
    const entities = s.entities as Record<string, unknown> | undefined;
    const rationale = entities?.confidence_rationale;
    if (typeof rationale === "string" && rationale) {
      parts.push(rationale);
      parts.push("");
    }
  }

  // Proposed Experiment
  if (s?.proposed_experiment) {
    parts.push("## Proposed Experiment");
    parts.push("");
    parts.push(s.proposed_experiment);
    parts.push("");
  }

  // Ranked Candidates
  const entities = s?.entities as Record<string, unknown> | undefined;
  const rawCandidates = entities?.ranked_candidates;
  if (Array.isArray(rawCandidates) && rawCandidates.length > 0) {
    const candidates = rawCandidates as RankedCandidate[];
    const included = candidates.filter((c) => !c.excluded);
    const excluded = candidates.filter((c) => c.excluded);

    if (included.length > 0) {
      parts.push("## Ranked Candidates");
      parts.push("");
      included.forEach((c, i) => {
        const rank = c.rank ?? i + 1;
        const gene = c.gene ?? "";
        const reasoning = c.reasoning ?? "";
        const source = c.source ?? "";
        let line = `${rank}. **${gene}**`;
        if (reasoning) line += ` -- ${reasoning}`;
        if (source) line += ` _(source: ${source})_`;
        parts.push(line);
      });
      parts.push("");
    }

    if (excluded.length > 0) {
      parts.push("### Excluded");
      parts.push("");
      excluded.forEach((c) => {
        const gene = c.gene ?? "";
        const reasoning = c.reasoning ?? "";
        let line = `- **${gene}**`;
        if (reasoning) line += ` -- ${reasoning}`;
        parts.push(line);
      });
      parts.push("");
    }
  }

  // Flags
  const flags = result.discover?.flags;
  if (flags) {
    const veto = flags.VETO ?? [];
    const div = flags.DIVERGENCE ?? [];
    const ku = flags.KNOWN_UNKNOWNS ?? [];
    if (veto.length > 0 || div.length > 0 || ku.length > 0) {
      parts.push("## Flags");
      parts.push("");
      if (veto.length > 0) {
        parts.push("### VETO");
        veto.forEach((item) => parts.push(`- ${item}`));
        parts.push("");
      }
      if (div.length > 0) {
        parts.push("### DIVERGENCE");
        div.forEach((item) => parts.push(`- ${item}`));
        parts.push("");
      }
      if (ku.length > 0) {
        parts.push("### Known Unknowns");
        ku.forEach((item) => parts.push(`- ${item}`));
        parts.push("");
      }
    }
  }

  // Partner Spread
  const verdicts = finalVerdicts(result);
  const rebuttal = isRebuttalRound(result);
  if (verdicts.length > 0) {
    parts.push("## Partner Spread");
    parts.push("");
    verdicts.forEach((v) => {
      const conviction = v.conviction != null ? ` (conviction: ${v.conviction}/10)` : "";
      const stance = v.stance ? ` -- ${v.stance.toUpperCase()}` : "";
      parts.push(`### ${v.persona}${stance}${conviction}`);
      if (v.rationale) {
        parts.push(v.rationale);
      }
      if (rebuttal) {
        parts.push("");
        parts.push("_(round 2 rebuttal)_");
      }
      parts.push("");
    });
  }

  // Dossier Sources
  const dossier = result.discover?.dossier ?? [];
  if (dossier.length > 0) {
    parts.push("## Dossier Sources");
    parts.push("");
    parts.push("| Fact | Tier | Provenance | Source |");
    parts.push("|------|------|------------|--------|");
    dossier.forEach((f) => {
      const value = (f.value ?? "").replace(/\|/g, "\\|");
      const tier = f.tier ?? "";
      const prov = f.provenance ?? "";
      const src = (f.source ?? "").replace(/\|/g, "\\|");
      parts.push(`| ${value} | ${tier} | ${prov} | ${src} |`);
    });
    parts.push("");
  }

  parts.push("---");
  parts.push("_Sapphire -- Quiver Bioscience CNS drug-discovery firm_");
  parts.push("_Engine: run_live | Provenance preserved | No facts fabricated_");
  parts.push("");

  return parts.join("\n");
}

/** Write the synthesis to clipboard and optionally trigger a file download. */
export async function exportSynthesis(
  result: RunResult,
  opts?: { download?: boolean },
): Promise<void> {
  const md = buildSynthesisMarkdown(result);

  await navigator.clipboard.writeText(md);

  if (opts?.download) {
    const date = new Date().toISOString().split("T")[0];
    const id = result.engagement_id ?? "run";
    const filename = `sapphire-${id}-${date}.md`;

    const blob = new Blob([md], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }
}
