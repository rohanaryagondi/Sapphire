"use client";
import * as React from "react";
import type { RunResult, Verdict } from "@/lib/types";
import { cn, stanceKind } from "@/lib/utils";
import { ProvChip } from "@/components/ui/chips";
import { useFirm } from "@/lib/store";
import { SectionHeader } from "./section";

type Kind = "advance" | "caution" | "block" | "neutral";

const KIND_META: Record<Kind, { label: string; bar: string; badge: string; dot: string }> = {
  advance: {
    label: "Supportive",
    bar: "bg-[var(--color-ok)]",
    badge: "bg-[var(--color-ok-bg)] text-[var(--color-ok)]",
    dot: "bg-[var(--color-ok)]",
  },
  caution: {
    label: "Conditional",
    bar: "bg-[var(--color-warn)]",
    badge: "bg-[var(--color-warn-bg)] text-[var(--color-warn)]",
    dot: "bg-[var(--color-warn)]",
  },
  block: {
    label: "Skeptical",
    bar: "bg-[var(--color-danger)]",
    badge: "bg-[var(--color-danger-bg)] text-[var(--color-danger)]",
    dot: "bg-[var(--color-danger)]",
  },
  neutral: {
    label: "Neutral",
    bar: "bg-[var(--color-fg-faint)]",
    badge: "bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)]",
    dot: "bg-[var(--color-fg-faint)]",
  },
};

function convictionPct(c?: number): number | null {
  if (c == null) return null;
  const pct = c <= 1 ? c * 100 : c;
  return Math.max(0, Math.min(100, Math.round(pct)));
}

function PersonaCard({ v, turnId }: { v: Verdict; turnId: string }) {
  const select = useFirm((s) => s.select);
  const selection = useFirm((s) => s.selection);
  const ok = v.status === "ok";
  const kind: Kind = ok ? stanceKind(v.stance) : "neutral";
  const meta = KIND_META[kind];
  const pct = convictionPct(v.conviction);
  const active =
    selection.kind === "verdict" &&
    selection.persona === v.persona &&
    selection.turnId === turnId;

  return (
    <button
      onClick={() => select({ kind: "verdict", persona: v.persona, turnId })}
      className={cn(
        "card-hover flex flex-col rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-panel)] p-2.5 text-left",
        active && "!border-[var(--color-accent)] shadow-[0_0_0_2px_var(--color-accent-soft)]",
      )}
    >
      <div className="truncate text-[11.5px] font-bold text-[var(--color-fg)]">
        {v.persona || "partner"}
      </div>
      {v.lens && (
        <div className="mb-2 mt-0.5 line-clamp-2 text-[10px] leading-snug text-[var(--color-fg-faint)]">
          {v.lens}
        </div>
      )}
      <span
        className={cn(
          "mt-auto inline-block w-fit rounded-[3px] px-1.5 py-0.5 text-[9.5px] font-bold",
          ok ? meta.badge : "bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)]",
        )}
      >
        {ok ? v.stance || meta.label : "Abstained"}
      </span>
      {ok && pct != null && (
        <div className="mt-2">
          <div className="h-[3px] rounded-full bg-[var(--color-border)]">
            <div
              className={cn("h-[3px] rounded-full", meta.bar)}
              style={{ width: `${pct}%` }}
            />
          </div>
          <div className="mt-1 text-[9.5px] text-[var(--color-fg-faint)]">
            Conviction {pct}%
          </div>
        </div>
      )}
    </button>
  );
}

function SpreadBar({ round }: { round: Verdict[] }) {
  const counts: Record<Kind, number> = { advance: 0, caution: 0, block: 0, neutral: 0 };
  for (const v of round) {
    const k: Kind = v.status === "ok" ? stanceKind(v.stance) : "neutral";
    counts[k] += 1;
  }
  const total = round.length || 1;
  const order: Kind[] = ["advance", "caution", "block", "neutral"];
  const present = order.filter((k) => counts[k] > 0);

  return (
    <div className="rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-panel)] p-3.5">
      <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.06em] text-[var(--color-fg-subtle)]">
        Spread — no forced consensus
      </div>
      <div className="flex h-2 overflow-hidden rounded-full">
        {present.map((k) => (
          <div
            key={k}
            className={cn("h-full", KIND_META[k].bar)}
            style={{ width: `${(counts[k] / total) * 100}%` }}
          />
        ))}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1">
        {present.map((k) => (
          <span key={k} className="flex items-center gap-1.5 text-[10.5px] text-[var(--color-fg-muted)]">
            <span className={cn("h-2 w-2 rounded-[2px]", KIND_META[k].dot)} />
            {KIND_META[k].label} ({counts[k]})
          </span>
        ))}
      </div>
    </div>
  );
}

function RebuttalCard({ v, turnId }: { v: Verdict; turnId: string }) {
  const select = useFirm((s) => s.select);
  const ok = v.status === "ok";
  const kind: Kind = ok ? stanceKind(v.stance) : "neutral";
  const meta = KIND_META[kind];
  const via = undefined;
  return (
    <button
      onClick={() => select({ kind: "verdict", persona: v.persona, turnId })}
      className={cn(
        "card-hover w-full rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-panel)] p-3 text-left",
        "border-l-[3px]",
      )}
      style={{ borderLeftColor: `var(--color-${kind === "advance" ? "ok" : kind === "block" ? "danger" : kind === "caution" ? "warn" : "border-strong"})` }}
    >
      <div className="mb-1 flex items-center gap-2">
        <span className="text-[11.5px] font-bold text-[var(--color-fg)]">{v.persona}</span>
        {ok && v.stance && (
          <span className={cn("rounded-[3px] px-1.5 py-0.5 text-[9.5px] font-bold", meta.badge)}>
            {v.stance}
          </span>
        )}
      </div>
      {v.rationale && (
        <p className="text-[12px] leading-relaxed text-[var(--color-fg-muted)]">
          {v.rationale}
        </p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {v.provenance && <ProvChip prov={v.provenance} via={via} />}
      </div>
    </button>
  );
}

export function Spread({ result, turnId }: { result: RunResult; turnId: string }) {
  const consult = result.consult ?? { round1: [] };
  const round1 = consult.round1 ?? [];
  const round2 = consult.round2 ?? [];
  const [tab, setTab] = React.useState<"r1" | "r2">("r1");
  if (!round1.length && !round2.length) return null;

  const hasR2 = round2.length > 0;

  return (
    <div>
      <SectionHeader
        label="Bucket 2 — Roundtable Spread"
        count={`${round1.length || round2.length} personas${hasR2 ? " · 2 rounds" : ""}`}
      />

      <div className="mb-3 flex gap-1.5">
        <RoundTab active={tab === "r1"} onClick={() => setTab("r1")}>
          Round 1 — Verdicts
        </RoundTab>
        {hasR2 && (
          <RoundTab active={tab === "r2"} onClick={() => setTab("r2")}>
            Round 2 — Rebuttal
          </RoundTab>
        )}
      </div>

      {tab === "r1" && round1.length > 0 && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {round1.map((v, i) => (
              <PersonaCard key={`${v.persona}_${i}`} v={v} turnId={turnId} />
            ))}
          </div>
          <SpreadBar round={round1} />
        </div>
      )}

      {tab === "r2" && (
        <div className="space-y-1.5">
          {round2.map((v, i) => (
            <RebuttalCard key={`${v.persona}_${i}`} v={v} turnId={turnId} />
          ))}
        </div>
      )}
    </div>
  );
}

function RoundTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "rounded-full border px-3 py-1 text-[11px] font-medium transition-colors",
        active
          ? "border-[var(--color-fg)] bg-[var(--color-fg)] text-white"
          : "border-[var(--color-border)] bg-[var(--color-panel)] text-[var(--color-fg-subtle)] hover:border-[var(--color-border-strong)]",
      )}
    >
      {children}
    </button>
  );
}
