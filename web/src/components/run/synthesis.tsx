"use client";
import * as React from "react";
import { Download, FlaskConical, Sparkles } from "lucide-react";
import type { RunResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { exportSynthesis } from "@/lib/export-synthesis";

interface RankedCandidate {
  rank?: number;
  gene?: string;
  reasoning?: string;
  source?: string;
  excluded?: boolean;
}

function confTone(conf: string): string {
  const c = conf.toLowerCase();
  if (/high|strong/.test(c)) return "text-[var(--color-ok)]";
  if (/low|weak/.test(c)) return "text-[var(--color-warn)]";
  return "text-[var(--color-fg-muted)]";
}

function CandidateRow({ c, rank }: { c: RankedCandidate; rank: number }) {
  return (
    <div className="flex gap-2 py-1">
      <span
        className={cn(
          "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-[4px] text-[10.5px] font-bold",
          c.excluded
            ? "bg-[rgba(248,81,73,0.12)] text-[var(--color-danger)]"
            : "bg-[rgba(63,185,80,0.12)] text-[var(--color-ok)]",
        )}
      >
        {c.excluded ? "X" : rank}
      </span>
      <div className="min-w-0 flex-1">
        <span className="text-[13px] font-semibold text-[var(--color-fg)]">
          {c.gene ?? ""}
        </span>
        {c.reasoning && (
          <p className="mt-0.5 text-[12.5px] leading-snug text-[var(--color-fg-muted)]">
            {c.reasoning}
          </p>
        )}
        {c.source && (
          <p className="mt-0.5 font-mono text-[10px] text-[var(--color-external)]">
            {c.source}
          </p>
        )}
      </div>
    </div>
  );
}

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
  const rawCandidates = entities?.ranked_candidates;
  const candidates: RankedCandidate[] = Array.isArray(rawCandidates)
    ? (rawCandidates as RankedCandidate[])
    : [];
  const included = candidates.filter((c) => !c.excluded);
  const excluded = candidates.filter((c) => c.excluded);

  const confidenceRationale =
    typeof entities?.confidence_rationale === "string"
      ? (entities.confidence_rationale as string)
      : null;

  return (
    <div className="relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-gradient-to-b from-[rgba(77,141,255,0.06)] to-[var(--color-panel)] p-4 shadow-[0_1px_0_rgba(255,255,255,0.03),0_18px_40px_-24px_rgba(77,141,255,0.4)]">
      <div className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-[radial-gradient(circle,rgba(77,141,255,0.18),transparent_70%)]" />
      <div className="relative">
        {/* Header row */}
        <div className="mb-2 flex items-center gap-1.5">
          <div className="flex flex-1 items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--color-accent)]">
            <Sparkles className="size-3" />
            Synthesis
          </div>
          <button
            onClick={handleExport}
            className="flex items-center gap-1 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-elevated)] px-2 py-1 text-[11px] text-[var(--color-fg-muted)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-fg)]"
            title="Copy synthesis to clipboard as cited Markdown"
          >
            <Download className="size-3" />
            {copied ? "Copied!" : "Export"}
          </button>
        </div>

        {/* Recommendation */}
        <p className="text-[15px] font-medium leading-relaxed text-[var(--color-fg)]">
          {s.recommendation || "--"}
        </p>

        {/* Confidence */}
        <div className="mt-2.5 flex items-center gap-1.5 text-[12px]">
          <span className="text-[var(--color-fg-subtle)]">Confidence</span>
          <span className={cn("font-semibold", confTone(s.confidence || ""))}>
            {s.confidence || "--"}
          </span>
        </div>
        {confidenceRationale && (
          <p className="mt-1 text-[12px] leading-snug text-[var(--color-fg-muted)]">
            {confidenceRationale}
          </p>
        )}

        {/* Ranked candidates */}
        {included.length > 0 && (
          <div className="mt-3 space-y-0.5">
            <div className="mb-1 text-[10.5px] font-medium uppercase tracking-[0.06em] text-[var(--color-fg-subtle)]">
              Ranked candidates
            </div>
            {included.map((c, i) => (
              <CandidateRow key={c.gene ?? i} c={c} rank={c.rank ?? i + 1} />
            ))}
          </div>
        )}

        {excluded.length > 0 && (
          <div className="mt-2.5 space-y-0.5">
            <div className="mb-1 text-[10.5px] font-medium uppercase tracking-[0.06em] text-[var(--color-fg-subtle)]">
              Excluded targets
            </div>
            {excluded.map((c, i) => (
              <CandidateRow key={c.gene ?? i} c={c} rank={0} />
            ))}
          </div>
        )}

        {/* Proposed experiment */}
        {s.proposed_experiment && (
          <div className="mt-3 rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-3">
            <div className="mb-1 flex items-center gap-1.5 text-[10.5px] font-medium uppercase tracking-[0.06em] text-[var(--color-fg-subtle)]">
              <FlaskConical className="size-3" />
              Proposed experiment
            </div>
            <p className="text-[13px] leading-relaxed text-[var(--color-fg-muted)]">
              {s.proposed_experiment}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
