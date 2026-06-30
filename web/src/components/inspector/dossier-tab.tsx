"use client";
import type { Turn } from "@/lib/store";
import { cn, isPlaceholderCitation, mockLabel, stripEmoji } from "@/lib/utils";
import { FlagChip, MockBadge } from "@/components/ui/chips";
import { useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { Fact } from "@/lib/types";

/**
 * FactCard — a single fact row in the dossier.
 * Tier/provenance/plane chips and DOIs are removed per the UI polish spec.
 * For EMET facts a terse "EMET" label is shown; for all others nothing.
 * The per-fact "ask" affordance is preserved when onAsk is provided.
 */
export function FactCard({
  fact,
  via,
  onAsk,
}: {
  fact: Fact;
  via?: string;
  /** WO-8 Phase 3: per-fact "ask" affordance (Info tab scoped side-chat) — when
   *  provided, a small "ask" button pre-fills the side-chat input scoped to
   *  just this fact. Omitted in contexts (e.g. a plain dossier dump) that have
   *  no side-chat. */
  onAsk?: (fact: Fact) => void;
}) {
  void via; // via kept in signature for backward compat; chip display removed
  const mock = mockLabel(fact.provenance, fact.value, fact.source);
  const placeholderSrc = isPlaceholderCitation(fact.source);
  // EMET facts show "EMET" only — no DOI, no BenchSci, no chip row.
  const sourceTerse = fact.provenance?.toLowerCase().includes("emet") ? "EMET" : null;
  return (
    <div
      className={cn(
        "rounded-[8px] border p-2.5 my-1 mx-0.5",
        mock
          ? "border-dashed border-[rgba(210,153,34,0.35)] bg-[rgba(210,153,34,0.04)]"
          : "border-[var(--color-border)] bg-[var(--color-panel)]",
      )}
    >
      <div className="flex items-start gap-2">
        <p className={cn("flex-1 text-[12px] leading-snug", mock ? "italic text-[var(--color-fg-muted)]" : "text-[var(--color-fg)]")}>
          {stripEmoji(fact.value)}
        </p>
        {onAsk && (
          <button
            onClick={() => onAsk(fact)}
            className="shrink-0 rounded-[5px] border border-[var(--color-border)] px-1.5 py-0.5 text-[10px] text-[var(--color-fg-subtle)] transition-colors hover:border-[var(--color-q-bd)] hover:text-[var(--color-q-text)]"
            title="Ask about this fact"
            aria-label="Ask about this fact"
          >
            ask
          </button>
        )}
      </div>
      {(mock || fact.flag || sourceTerse || placeholderSrc) && (
        <div className="mt-1.5 flex flex-wrap items-center gap-1">
          {mock && <MockBadge label={mock} />}
          {fact.flag && <FlagChip flag={fact.flag} />}
          {sourceTerse && (
            <span className="ml-0.5 text-[10px] text-[var(--color-fg-subtle)]">{sourceTerse}</span>
          )}
          {placeholderSrc && (
            <span className="ml-0.5 truncate text-[10px] italic text-[var(--color-fg-faint)]">placeholder</span>
          )}
        </div>
      )}
    </div>
  );
}

export function FactList({
  facts,
  via,
  onAsk,
}: {
  facts: Fact[];
  via?: string;
  onAsk?: (fact: Fact) => void;
}) {
  const parentRef = useRef<HTMLDivElement>(null);
  const shouldVirtualize = facts.length > 20;
  const virtualizer = useVirtualizer({
    count: facts.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 80,
    enabled: shouldVirtualize,
  });

  if (!shouldVirtualize) {
    return (
      <>
        {facts.map((f, i) => <FactCard key={i} fact={f} via={via} onAsk={onAsk} />)}
      </>
    );
  }

  return (
    <div ref={parentRef} style={{ overflow: "auto", maxHeight: 600 }}>
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {virtualizer.getVirtualItems().map((vi) => (
          <div key={vi.key} style={{ position: "absolute", top: vi.start, left: 0, right: 0 }}>
            <FactCard fact={facts[vi.index]!} via={via} onAsk={onAsk} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function DossierTab({ turn }: { turn?: Turn }) {
  if (!turn?.result) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center">
        <p className="text-[12.5px] text-[var(--color-fg-subtle)]">
          Dossier will appear when the run completes.
        </p>
      </div>
    );
  }

  const dossier = turn.result.discover?.dossier ?? [];
  const via = turn.result._via === "replay" || turn.result._replay ? "replay" : undefined;
  const internal = dossier.filter((f) => f.plane === "internal" || (f.provenance ?? "").toLowerCase().includes("moat"));
  const external = dossier.filter((f) => !(f.plane === "internal" || (f.provenance ?? "").toLowerCase().includes("moat")));

  if (!dossier.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center">
        <p className="text-[12.5px] text-[var(--color-fg-subtle)]">No facts in dossier.</p>
      </div>
    );
  }

  return (
    <div className="p-2">
      {internal.length > 0 && (
        <>
          <div className="mb-1 mt-2 px-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-fg-subtle)]">
            Internal moat findings
          </div>
          <FactList facts={internal} via={via} />
        </>
      )}
      {external.length > 0 && (
        <>
          <div className="mb-1 mt-3 px-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-fg-subtle)]">
            External evidence
          </div>
          <FactList facts={external} via={via} />
        </>
      )}
    </div>
  );
}
