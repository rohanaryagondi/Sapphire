"use client";
import * as React from "react";
import { Globe, Lock } from "lucide-react";
import type { RunResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { FlagChip, ProvChip, TierChip } from "@/components/ui/chips";
import { useFirm } from "@/lib/store";
import { SectionHeader } from "./section";
import type { Source } from "@/lib/citations";

type PlaneKey = "external" | "internal";

function FactRow({
  source,
  turnId,
  via,
}: {
  source: Source;
  turnId: string;
  via?: string;
}) {
  const fact = source.fact;
  const select = useFirm((s) => s.select);
  const selection = useFirm((s) => s.selection);
  const active =
    selection.kind === "fact" &&
    selection.index === source.index &&
    selection.turnId === turnId;

  return (
    <button
      id={`src-${turnId}-${source.num}`}
      onClick={() => select({ kind: "fact", index: source.index, turnId })}
      className={cn(
        "card-hover flex w-full items-start gap-3 rounded-[var(--radius)] border bg-[var(--color-panel)] p-3 text-left",
        source.internal
          ? "border-l-[3px] border-l-[var(--color-internal-border)] border-y-[var(--color-border)] border-r-[var(--color-border)]"
          : "border-l-[3px] border-l-[var(--color-external-border)] border-y-[var(--color-border)] border-r-[var(--color-border)]",
        active && "!border-[var(--color-accent)] shadow-[0_0_0_2px_var(--color-accent-soft)]",
      )}
    >
      <span
        className={cn(
          "mt-px flex h-[18px] min-w-[20px] items-center justify-center rounded-[4px] px-1 font-mono text-[10px] font-bold",
          source.internal
            ? "bg-[var(--color-internal-bg)] text-[var(--color-internal)]"
            : "bg-[var(--color-accent-soft)] text-[var(--color-accent)]",
        )}
      >
        {source.internal ? `🔒${source.num}` : source.num}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-[13px] leading-[1.55] text-[var(--color-fg)]">
          {fact.value}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <TierChip tier={fact.tier} />
          <ProvChip prov={fact.provenance} via={via} />
          {fact.flag && <FlagChip flag={fact.flag} />}
          {fact.source && (
            <span className="truncate text-[10.5px] text-[var(--color-fg-subtle)]">
              {fact.source}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}

export function Dossier({
  result,
  sources,
  turnId,
}: {
  result: RunResult;
  sources: Source[];
  turnId: string;
}) {
  const via = result._via === "replay" || result._replay ? "replay" : undefined;
  const external = sources.filter((s) => !s.internal);
  const internal = sources.filter((s) => s.internal);
  // default to whichever plane has facts; prefer external
  const [plane, setPlane] = React.useState<PlaneKey>(
    external.length ? "external" : "internal",
  );
  if (!sources.length) return null;

  const shown = plane === "external" ? external : internal;

  return (
    <div>
      <SectionHeader label="Bucket 1 — Fact Dossier" count={`${sources.length} facts`} />

      <div className="mb-3 flex overflow-hidden rounded-[var(--radius)] border border-[var(--color-border)]">
        <PlaneTab
          active={plane === "external"}
          onClick={() => setPlane("external")}
          icon={<Globe className="size-3.5" />}
          label="External"
          count={external.length}
          accent="external"
        />
        <div className="w-px bg-[var(--color-border)]" />
        <PlaneTab
          active={plane === "internal"}
          onClick={() => setPlane("internal")}
          icon={<Lock className="size-3.5" />}
          label="Internal moat"
          count={internal.length}
          accent="internal"
        />
      </div>

      {shown.length === 0 ? (
        <p className="rounded-[var(--radius)] border border-dashed border-[var(--color-border)] px-3 py-4 text-center text-[12px] text-[var(--color-fg-subtle)]">
          No facts on this plane.
        </p>
      ) : (
        <div className="flex flex-col gap-1.5">
          {shown.map((src) => (
            <FactRow key={src.num} source={src} turnId={turnId} via={via} />
          ))}
        </div>
      )}
    </div>
  );
}

function PlaneTab({
  active,
  onClick,
  icon,
  label,
  count,
  accent,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  count: number;
  accent: PlaneKey;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-1 items-center justify-center gap-1.5 px-3 py-2 text-[11.5px] font-medium transition-colors",
        active
          ? "bg-[var(--color-bg-subtle)] font-semibold text-[var(--color-fg)]"
          : "bg-[var(--color-panel)] text-[var(--color-fg-subtle)] hover:bg-[var(--color-bg-subtle)]",
      )}
    >
      {icon}
      {label}
      <span
        className={cn(
          "rounded-[3px] px-1.5 py-0.5 text-[9.5px] font-bold",
          accent === "internal"
            ? "bg-[var(--color-internal-bg)] text-[var(--color-internal)]"
            : "bg-[var(--color-external-bg)] text-[var(--color-external)]",
        )}
      >
        {count}
      </span>
    </button>
  );
}
