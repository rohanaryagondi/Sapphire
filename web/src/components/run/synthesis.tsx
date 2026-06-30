"use client";
import * as React from "react";
import type { RunResult, Fact, Verdict } from "@/lib/types";
import { cn, stanceKind, stripEmoji } from "@/lib/utils";
import { finalVerdicts } from "@/lib/verdicts";
import { exportSynthesis } from "@/lib/export-synthesis";

/* ── helpers ────────────────────────────────────────────────────────────────── */

function stanceDot(stance: string): string {
  const k = stanceKind(stance);
  if (k === "advance") return "bg-[var(--color-ok)]";
  if (k === "block") return "bg-[var(--color-danger)]";
  if (k === "caution") return "bg-[var(--color-warn)]";
  return "bg-[var(--color-fg-subtle)]";
}

function stanceText(stance: string): { text: string; cls: string } {
  const k = stanceKind(stance);
  if (k === "advance") return { text: stance, cls: "text-[var(--color-ok)]" };
  if (k === "block") return { text: stance, cls: "text-[var(--color-danger)]" };
  if (k === "caution") return { text: stance, cls: "text-[var(--color-warn)]" };
  return { text: stance || "neutral", cls: "text-[var(--color-fg-muted)]" };
}

/** Violet section heading for the narrative report. */
function Section({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-1 text-[10.5px] font-semibold uppercase tracking-[0.07em] text-[var(--color-accent)]">
      {children}
    </div>
  );
}

/** Derive a plain source word from provenance/source strings. */
function plainSource(provenance: string, source: string): string {
  const p = provenance.toLowerCase();
  if (/emet/.test(p)) return "EMET";
  if (/moat|internal|cns[_-]?dfp/.test(p)) return "Internal moat";
  if (/qmodel|q-model|q_model/.test(p)) return "Q-Models";
  if (/aso[-_]?tox/.test(p)) return "ASO-Tox";
  if (/semantic|regulatory|dea|patent|ip|payer|financial|manufacturing|cmc|advocacy|kol|social|policy|legislative|reputational|clinical[_-]?trial|post[_-]?market/.test(p)) {
    return "Semantic agent";
  }
  if (source) return source.replace(/^PMID:\d+$/, "EMET").replace(/^doi:.+/i, "External");
  return provenance || "External";
}

/** Group dossier facts by provenance bucket. */
function groupFacts(dossier: Fact[]): {
  internal: Fact[];
  external: Record<string, Fact[]>;
} {
  const internal: Fact[] = [];
  const external: Record<string, Fact[]> = {};

  for (const f of dossier) {
    const p = String(f.provenance ?? "").toLowerCase();
    if (/moat|internal|cns[_-]?dfp/.test(p)) {
      internal.push(f);
    } else {
      const label = plainSource(f.provenance ?? "", f.source ?? "");
      if (!external[label]) external[label] = [];
      external[label].push(f);
    }
  }
  return { internal, external };
}

/** Truncate a string to ~n chars, ending at a word boundary. */
function trunc(s: string, n = 220): string {
  if (s.length <= n) return s;
  const cut = s.lastIndexOf(" ", n);
  return s.slice(0, cut > 0 ? cut : n) + "...";
}

/* ── sub-components ─────────────────────────────────────────────────────────── */

function FactProse({ facts, label }: { facts: Fact[]; label: string }) {
  if (!facts.length) return null;
  return (
    <div className="mb-2">
      <span className="text-[12.5px] font-semibold text-[var(--color-fg)]">{label}</span>
      <ul className="mt-1 list-none space-y-1 pl-0">
        {facts.slice(0, 12).map((f, i) => (
          <li key={i} className="flex gap-2 text-[15px] leading-relaxed text-[var(--color-fg-muted)]">
            <span className="mt-[7px] shrink-0 text-[var(--color-fg-faint)]">·</span>
            <span>
              {stripEmoji(trunc(f.value ?? ""))}
              {f.source && (
                <span className="ml-1 text-[11.5px] text-[var(--color-fg-faint)]">
                  ({plainSource(f.provenance ?? "", f.source)})
                </span>
              )}
            </span>
          </li>
        ))}
        {facts.length > 12 && (
          <li className="text-[12px] text-[var(--color-fg-faint)] pl-4">
            + {facts.length - 12} more
          </li>
        )}
      </ul>
    </div>
  );
}

/* ── main component ─────────────────────────────────────────────────────────── */

/**
 * Synthesis -- the full narrative firm report.
 * Sections: Bottom line, What the firm found (evidence), How partners weighed in,
 * Open questions, Recommended next step.
 * Replaces the old card-chrome dashboard; folds in what Spread used to show.
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

  // Evidence
  const dossier = result.discover?.dossier ?? [];
  const { internal: internalFacts, external: externalGroups } = groupFacts(dossier);

  // Partners
  const allVerdicts: Verdict[] = finalVerdicts(result);
  const verdicts = allVerdicts.filter((v) => v.status === "ok");
  const simVerdicts = allVerdicts.filter((v) => v.status !== "ok");

  // Open questions
  const knownUnknowns: string[] = (() => {
    const raw = result.discover?.flags?.KNOWN_UNKNOWNS;
    return Array.isArray(raw) ? raw.filter((x) => typeof x === "string") : [];
  })();
  const followUpQuestions: string[] = (() => {
    const raw = entities?.follow_up_questions;
    return Array.isArray(raw) ? (raw as string[]).filter((x) => typeof x === "string") : [];
  })();
  const openItems = [...knownUnknowns, ...followUpQuestions];

  const hasEvidence = internalFacts.length > 0 || Object.keys(externalGroups).length > 0;

  return (
    <div className="space-y-5">
      {/* Export button -- de-emphasized, top-right */}
      <div className="flex justify-end">
        <button
          onClick={handleExport}
          className="text-[11px] text-[var(--color-fg-faint)] transition-colors hover:text-[var(--color-fg-muted)]"
          title="Copy full report to clipboard as Markdown"
        >
          {copied ? "Copied!" : "Export"}
        </button>
      </div>

      {/* 1. Bottom line */}
      {(s.recommendation || s.confidence) && (
        <div>
          <Section>Bottom line</Section>
          {s.recommendation && (
            <p className="text-[15px] font-medium leading-relaxed text-[var(--color-fg)]">
              {stripEmoji(s.recommendation)}
            </p>
          )}
          {s.confidence && (
            <p className="mt-1 text-[14px] leading-relaxed text-[var(--color-fg-muted)]">
              Confidence: <span className="font-medium">{stripEmoji(s.confidence)}</span>
              {confidenceRationale ? `. ${stripEmoji(confidenceRationale)}` : "."}
            </p>
          )}
        </div>
      )}

      {/* 2. What the firm found (evidence) */}
      {hasEvidence && (
        <div>
          <Section>What the firm found</Section>
          <FactProse facts={internalFacts} label="Internal moat (Quiver CNS_DFP)" />
          {Object.entries(externalGroups).map(([label, facts]) => (
            <FactProse key={label} facts={facts} label={label} />
          ))}
        </div>
      )}

      {/* 3. How the partners weighed in */}
      {(verdicts.length > 0 || simVerdicts.length > 0) && (
        <div>
          <Section>How the partners weighed in</Section>
          {simVerdicts.length > 0 && verdicts.length === 0 && (
            <p className="mb-1.5 text-[13px] text-[var(--color-fg-faint)]">
              Partner verdicts are simulated for this run.
            </p>
          )}
          <div className="space-y-2">
            {verdicts.map((v, i) => {
              const { text, cls } = stanceText(v.stance ?? "");
              return (
                <div key={`${v.persona}_${i}`} className="flex items-start gap-2">
                  <span
                    className={cn(
                      "mt-[7px] inline-block h-2 w-2 shrink-0 rounded-full",
                      stanceDot(v.stance ?? ""),
                    )}
                  />
                  <p className="text-[15px] leading-relaxed text-[var(--color-fg-muted)]">
                    <span className="font-semibold text-[var(--color-fg)]">
                      {stripEmoji(v.persona ?? "")}
                    </span>
                    {" -- "}
                    <span className={cn("font-semibold", cls)}>{stripEmoji(text)}</span>
                    {v.rationale ? `. ${stripEmoji(v.rationale)}` : "."}
                    {v.revised && (
                      <span className="ml-1 text-[11.5px] text-[var(--color-warn)]">(revised r2)</span>
                    )}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 4. Open questions */}
      {openItems.length > 0 && (
        <div>
          <Section>Open questions</Section>
          <ul className="list-none space-y-1 pl-0">
            {openItems.map((q, i) => (
              <li key={i} className="flex gap-1.5">
                <span className="mt-[6px] text-[var(--color-fg-faint)]">·</span>
                <span className="text-[15px] leading-relaxed text-[var(--color-fg-muted)]">
                  {stripEmoji(q)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 5. Recommended next step */}
      {s.proposed_experiment && (
        <div>
          <Section>Recommended next step</Section>
          <p className="text-[15px] leading-relaxed text-[var(--color-fg-muted)]">
            {stripEmoji(s.proposed_experiment)}
          </p>
        </div>
      )}
    </div>
  );
}
