"use client";
import { useState } from "react";
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
  // so it can never be mistaken for a real (Quiver data / emet-live / corpus) fact.
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

/** Collapsible toggle row — shared by L1 and L2 headings. */
function CollapseToggle({
  open,
  onToggle,
  label,
  count,
  indent = false,
}: {
  open: boolean;
  onToggle: () => void;
  label: string;
  count: number;
  indent?: boolean;
}) {
  return (
    <button
      onClick={onToggle}
      className={cn(
        "flex w-full items-center gap-1.5 text-left",
        indent ? "mt-2 first:mt-0 py-1" : "mb-1 py-0.5",
      )}
    >
      <ChevronRight
        className={cn(
          "size-3 shrink-0 text-[var(--color-fg-subtle)] transition-transform duration-150",
          open && "rotate-90",
        )}
      />
      <span className="flex-1 text-xs font-semibold uppercase tracking-wide text-[var(--color-fg-subtle)]">
        {label}
      </span>
      <span className="rounded-full bg-[var(--color-border)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--color-fg-muted)]">
        {count}
      </span>
    </button>
  );
}

/**
 * Derive a source-group key from a fact's provenance, for grouping External evidence.
 * Returns a short human label.
 */
function externalGroupKey(fact: Fact): string {
  const p = String(fact.provenance ?? "").toLowerCase();
  if (p.startsWith("emet")) return "EMET";
  if (p === "qmodels" || p.startsWith("qmodels")) return "External Models";
  if (p === "moat-real" || p.startsWith("moat")) return "Quiver data";
  if (p === "corpus" || p === "gnomad" || p === "gtex" || p === "interpro" || p === "gprofiler")
    return "Curated datasets";
  // Semantic agents — named provenance values like "fda-institutional-memory" etc.
  if (p.length > 0 && p !== "simulated" && p !== "mock") return "Semantic agents";
  return "Other";
}

/** A small collapsible group within External evidence (by source). Default collapsed. */
function SourceGroup({
  label,
  items,
  turnId,
}: {
  label: string;
  items: Array<{ fact: Fact; index: number }>;
  turnId: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="ml-1 border-l border-[var(--color-border)] pl-2.5">
      <CollapseToggle
        open={open}
        onToggle={() => setOpen((v) => !v)}
        label={label}
        count={items.length}
        indent
      />
      {open && (
        <div className="mt-1 space-y-1.5">
          {items.map(({ fact, index }) => (
            <FactCard key={index} fact={fact} index={index} turnId={turnId} />
          ))}
        </div>
      )}
    </div>
  );
}

/** Collapsible L2 section for Quiver data or External evidence. Default collapsed. */
function Section({
  label,
  items,
  turnId,
  groupBySource = false,
}: {
  label: string;
  items: Array<{ fact: Fact; index: number }>;
  turnId: string;
  groupBySource?: boolean;
}) {
  const [open, setOpen] = useState(false);

  // Build source groups for external evidence
  const groups: Map<string, Array<{ fact: Fact; index: number }>> = new Map();
  if (groupBySource) {
    for (const item of items) {
      const key = externalGroupKey(item.fact);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(item);
    }
  }

  return (
    <div className="mt-2 first:mt-0">
      <CollapseToggle
        open={open}
        onToggle={() => setOpen((v) => !v)}
        label={label}
        count={items.length}
        indent
      />
      {open && (
        <div className="mt-1 ml-1 border-l border-[var(--color-border)] pl-2.5">
          {groupBySource ? (
            <div className="space-y-1">
              {Array.from(groups.entries()).map(([groupLabel, groupItems]) => (
                <SourceGroup
                  key={groupLabel}
                  label={groupLabel}
                  items={groupItems}
                  turnId={turnId}
                />
              ))}
            </div>
          ) : (
            <div className="space-y-1.5">
              {items.map(({ fact, index }) => (
                <FactCard key={index} fact={fact} index={index} turnId={turnId} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Single-column cited fact dossier.
 * LEVEL 1: "Cited fact dossier" toggle — default COLLAPSED.
 * LEVEL 2: "Quiver data" / "External evidence" — each collapsible, default collapsed.
 * LEVEL 3 (External evidence only): grouped by source agent, each collapsible, default collapsed.
 */
export function Dossier({ result, turnId }: { result: RunResult; turnId: string }) {
  const [open, setOpen] = useState(false);

  const dossier = result.discover?.dossier ?? [];
  if (!dossier.length) return null;

  const indexed = dossier.map((fact, index) => ({ fact, index }));
  const internal = indexed.filter(
    (x) =>
      x.fact.plane === "internal" ||
      (x.fact.provenance ?? "").toLowerCase().includes("moat"),
  );
  const external = indexed.filter(
    (x) =>
      !(
        x.fact.plane === "internal" ||
        (x.fact.provenance ?? "").toLowerCase().includes("moat")
      ),
  );

  return (
    <div
      data-testid="dossier-root"
      className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)]/40 p-3"
    >
      {/* LEVEL 1 toggle */}
      <button
        data-testid="dossier-toggle"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left"
      >
        <ChevronRight
          className={cn(
            "size-3.5 shrink-0 text-[var(--color-fg-subtle)] transition-transform duration-150",
            open && "rotate-90",
          )}
        />
        <span className="flex-1 text-[11px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
          Cited fact dossier
        </span>
        <span className="rounded-full bg-[var(--color-border)] px-1.5 py-0.5 text-[10px] font-medium text-[var(--color-fg-muted)]">
          {dossier.length}
        </span>
      </button>

      {/* LEVEL 2 sections — visible only when L1 is open */}
      {open && (
        <div className="mt-2" data-testid="dossier-body">
          {internal.length > 0 && (
            <Section
              label="Quiver data"
              items={internal}
              turnId={turnId}
              groupBySource={false}
            />
          )}
          {external.length > 0 && (
            <Section
              label="External evidence"
              items={external}
              turnId={turnId}
              groupBySource={true}
            />
          )}
        </div>
      )}
    </div>
  );
}
