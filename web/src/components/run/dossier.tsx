"use client";
import { ChevronRight } from "lucide-react";
import type { Fact, RunResult } from "@/lib/types";
import { cn, isPlaceholderCitation, mockLabel, stripEmoji } from "@/lib/utils";
import { FlagChip, MockBadge } from "@/components/ui/chips";
import { useFirm } from "@/lib/store";

/** A single clickable fact row — no tier/provenance/plane chips, no DOI/PMID noise. */
function FactCard({
  fact,
  index,
  turnId,
}: {
  fact: Fact;
  index: number;
  turnId: string;
}) {
  const select = useFirm((s) => s.select);
  const selection = useFirm((s) => s.selection);
  const active =
    selection.kind === "fact" && selection.index === index && selection.turnId === turnId;
  // honesty: a mock/stub/simulated fact gets a muted card + an unmistakable badge,
  // so it can never be mistaken for a real (moat-real / emet-live / corpus) fact.
  const mock = mockLabel(fact.provenance, fact.value, fact.source);
  // EMET facts show "EMET" only; all others show nothing (chips removed).
  const sourceTerse = fact.provenance?.toLowerCase().includes("emet") ? "EMET" : null;
  return (
    <button
      onClick={() => select({ kind: "fact", index, turnId })}
      className={cn(
        "card-hover group w-full rounded-[var(--radius)] border p-2.5 text-left",
        mock
          ? "border-dashed border-[rgba(210,153,34,0.35)] bg-[var(--color-bg-subtle)]/40 opacity-80"
          : "border-[var(--color-border)] bg-[var(--color-panel)]",
        active && "border-[var(--color-border-focus)] bg-[var(--color-panel-raised)] opacity-100",
      )}
    >
      <div className="flex items-start gap-2">
        <p
          className={cn(
            "flex-1 text-[13px] leading-snug",
            mock ? "text-[var(--color-fg-muted)] italic" : "text-[var(--color-fg)]",
          )}
        >
          {stripEmoji(fact.value)}
        </p>
        <ChevronRight className="mt-0.5 size-3.5 shrink-0 text-[var(--color-fg-faint)] transition-colors group-hover:text-[var(--color-fg-subtle)]" />
      </div>
      {(mock || fact.flag || sourceTerse) && (
        <div className="mt-1.5 flex flex-wrap items-center gap-1">
          {mock && <MockBadge label={mock} />}
          {fact.flag && <FlagChip flag={fact.flag} />}
          {sourceTerse && (
            <span className="ml-0.5 text-[10.5px] text-[var(--color-fg-subtle)]">{sourceTerse}</span>
          )}
          {fact.source && isPlaceholderCitation(fact.source) && (
            <span
              className="ml-0.5 truncate text-[10.5px] italic text-[var(--color-fg-faint)]"
              title="Placeholder citation — not a real reference."
            >
              placeholder
            </span>
          )}
        </div>
      )}
    </button>
  );
}

/** Section heading for Internal moat / External evidence grouping. */
function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-1.5 mt-3 first:mt-0 text-xs font-semibold uppercase tracking-wide text-[var(--color-fg-subtle)]">
      {children}
    </div>
  );
}

/** Single-column cited fact dossier, grouped into Internal moat / External evidence sections. */
export function Dossier({ result, turnId }: { result: RunResult; turnId: string }) {
  const dossier = result.discover?.dossier ?? [];
  const via = result._via === "replay" || result._replay ? "replay" : undefined;
  void via; // via used by FactCard via source honesty (not chip rendering)
  if (!dossier.length) return null;

  const indexed = dossier.map((fact, index) => ({ fact, index }));
  const internal = indexed.filter((x) => x.fact.plane === "internal" || (x.fact.provenance ?? "").toLowerCase().includes("moat"));
  const external = indexed.filter((x) => !(x.fact.plane === "internal" || (x.fact.provenance ?? "").toLowerCase().includes("moat")));

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)]/40 p-3">
      <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
        Cited fact dossier
      </div>
      {internal.length > 0 && (
        <>
          <SectionHeading>Internal moat findings</SectionHeading>
          <div className="space-y-1.5">
            {internal.map(({ fact, index }) => (
              <FactCard key={index} fact={fact} index={index} turnId={turnId} />
            ))}
          </div>
        </>
      )}
      {external.length > 0 && (
        <>
          <SectionHeading>External evidence</SectionHeading>
          <div className="space-y-1.5">
            {external.map(({ fact, index }) => (
              <FactCard key={index} fact={fact} index={index} turnId={turnId} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
