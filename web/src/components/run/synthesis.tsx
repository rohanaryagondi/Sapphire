"use client";
import * as React from "react";
import type { RunResult, Verdict } from "@/lib/types";
import { cn, stanceKind, stripEmoji } from "@/lib/utils";
import { finalVerdicts } from "@/lib/verdicts";
import { exportSynthesis } from "@/lib/export-synthesis";

/** Map stance kind to a colored dot class. */
function stanceDot(stance: string): string {
  const k = stanceKind(stance);
  if (k === "advance") return "bg-[var(--color-ok)]";
  if (k === "block") return "bg-[var(--color-danger)]";
  if (k === "caution") return "bg-[var(--color-warn)]";
  return "bg-[var(--color-fg-subtle)]";
}

/** One-word colored stance label for the partner narrative. */
function stanceText(stance: string): { text: string; cls: string } {
  const k = stanceKind(stance);
  if (k === "advance") return { text: stance, cls: "text-[var(--color-ok)]" };
  if (k === "block") return { text: stance, cls: "text-[var(--color-danger)]" };
  if (k === "caution") return { text: stance, cls: "text-[var(--color-warn)]" };
  return { text: stance || "neutral", cls: "text-[var(--color-fg-muted)]" };
}

function confTone(conf: string): string {
  const c = conf.toLowerCase();
  if (/high|strong/.test(c)) return "text-[var(--color-ok)]";
  if (/low|weak/.test(c)) return "text-[var(--color-warn)]";
  return "text-[var(--color-fg-muted)]";
}

/** Section heading for the narrative report. */
function Section({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-0.5 text-[10.5px] font-semibold uppercase tracking-[0.07em] text-[var(--color-accent)]">
      {children}
    </div>
  );
}

interface RankedCandidate {
  rank?: number;
  gene?: string;
  reasoning?: string;
  source?: string;
  excluded?: boolean;
}

/**
 * Synthesis — flowing 15px narrative report replacing the old card/box dashboard.
 * Sections: Recommendation, Why (rationale), Where partners land (narrative spread),
 * Confidence, Open questions, Proposed next experiment.
 * All sections degrade gracefully when data is absent.
 */
export function Synthesis({ result }: { result: RunResult }) {
  const s = result.synthesize;
  const [copied, setCopied] = React.useState(false);

  const handleExport = React.useCallback(() => {
    exportSynthesis(result).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [result]);

  if (!s) return null;

  const entities = s.entities as Record<string, unknown> | undefined;

  const confidenceRationale =
    typeof entities?.confidence_rationale === "string"
      ? (entities.confidence_rationale as string)
      : null;

  const rawCandidates = entities?.ranked_candidates;
  const candidates: RankedCandidate[] = Array.isArray(rawCandidates)
    ? (rawCandidates as RankedCandidate[])
    : [];
  const included = candidates.filter((c) => !c.excluded);

  const knownUnknowns: string[] = (() => {
    const raw = result.discover?.flags?.KNOWN_UNKNOWNS;
    return Array.isArray(raw) ? raw.filter((x) => typeof x === "string") : [];
  })();
  const followUpQuestions: string[] = (() => {
    const raw = entities?.follow_up_questions;
    return Array.isArray(raw) ? (raw as string[]).filter((x) => typeof x === "string") : [];
  })();
  const openItems = [...knownUnknowns, ...followUpQuestions];

  const verdicts: Verdict[] = finalVerdicts(result).filter((v) => v.status === "ok");

  return (
    <div className="space-y-3.5 rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-panel)] p-4">
      {/* header */}
      <div className="flex items-center justify-between">
        <span className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-[var(--color-accent)]">
          Synthesis
        </span>
        <button
          onClick={handleExport}
          className="text-[11px] text-[var(--color-fg-muted)] transition-colors hover:text-[var(--color-fg)]"
          title="Copy synthesis to clipboard as cited Markdown"
        >
          {copied ? "Copied!" : "Export"}
        </button>
      </div>

      {/* 1. Recommendation */}
      {s.recommendation && (
        <div>
          <Section>Recommendation</Section>
          <p className="text-[15px] font-medium leading-relaxed text-[var(--color-fg)]">
            {stripEmoji(s.recommendation)}
          </p>
        </div>
      )}

      {/* 2. Why (confidence_rationale as synthesized rationale paragraph) */}
      {confidenceRationale && (
        <div>
          <Section>Why</Section>
          <p className="text-[15px] leading-relaxed text-[var(--color-fg-muted)]">
            {stripEmoji(confidenceRationale)}
          </p>
        </div>
      )}

      {/* 3. Where the partners land — narrative spread */}
      {verdicts.length > 0 && (
        <div>
          <Section>Where the partners land</Section>
          <div className="space-y-1.5">
            {verdicts.map((v, i) => {
              const { text, cls } = stanceText(v.stance ?? "");
              return (
                <div key={`${v.persona}_${i}`} className="flex items-start gap-2">
                  <span className={cn("mt-[5px] inline-block h-2 w-2 shrink-0 rounded-full", stanceDot(v.stance ?? ""))} />
                  <p className="text-[15px] leading-relaxed text-[var(--color-fg-muted)]">
                    <span className="font-semibold text-[var(--color-fg)]">{v.persona}</span>
                    {" — "}
                    <span className={cn("font-semibold", cls)}>{stripEmoji(text)}</span>
                    {v.rationale ? `. ${stripEmoji(v.rationale)}` : "."}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 4. Confidence */}
      {s.confidence && (
        <div>
          <Section>Confidence</Section>
          <p className="text-[15px] leading-relaxed">
            <span className={cn("font-semibold", confTone(s.confidence))}>
              {stripEmoji(s.confidence)}
            </span>
            {" — "}
            <span className="text-[var(--color-fg-muted)]">
              {confidenceRationale ? "" : "no rationale recorded"}
            </span>
          </p>
        </div>
      )}

      {/* 5. Open questions */}
      {openItems.length > 0 && (
        <div>
          <Section>Open questions</Section>
          <ul className="list-none space-y-1 pl-0">
            {openItems.map((q, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="mt-[6px] text-[var(--color-fg-faint)]">·</span>
                <span className="text-[15px] leading-relaxed text-[var(--color-fg-muted)]">{stripEmoji(q)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 6. Proposed next experiment */}
      {s.proposed_experiment && (
        <div>
          <Section>Proposed next experiment</Section>
          <p className="text-[15px] leading-relaxed text-[var(--color-fg-muted)]">
            {stripEmoji(s.proposed_experiment)}
          </p>
        </div>
      )}

      {/* Ranked candidates (kept as compact addendum if present) */}
      {included.length > 0 && (
        <div>
          <Section>Ranked candidates</Section>
          <ol className="list-none space-y-1 pl-0">
            {included.map((c, i) => (
              <li key={c.gene ?? i} className="flex gap-2">
                <span className="shrink-0 font-mono text-[11.5px] text-[var(--color-fg-faint)]">{c.rank ?? i + 1}.</span>
                <p className="text-[15px] leading-relaxed text-[var(--color-fg-muted)]">
                  <span className="font-semibold text-[var(--color-fg)]">{c.gene ?? ""}</span>
                  {c.reasoning ? ` — ${stripEmoji(c.reasoning)}` : ""}
                </p>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  );
}
