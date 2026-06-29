"use client";
import { ChevronRight, Globe, Lock } from "lucide-react";
import type { Fact, RunResult } from "@/lib/types";
import { cn, isPlaceholderCitation, mockLabel } from "@/lib/utils";
import { FlagChip, MockBadge, PlaneChip, ProvChip, TierChip } from "@/components/ui/chips";
import { useFirm } from "@/lib/store";

function FactCard({
  fact,
  index,
  turnId,
  via,
}: {
  fact: Fact;
  index: number;
  turnId: string;
  via?: string;
}) {
  const select = useFirm((s) => s.select);
  const selection = useFirm((s) => s.selection);
  const active =
    selection.kind === "fact" && selection.index === index && selection.turnId === turnId;
  // honesty: a mock/stub/simulated fact gets a muted card + an unmistakable badge,
  // so it can never be mistaken for a real (moat-real / emet-live / corpus) fact.
  const mock = mockLabel(fact.provenance, fact.value, fact.source);
  const placeholderSrc = isPlaceholderCitation(fact.source);
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
          {fact.value}
        </p>
        <ChevronRight className="mt-0.5 size-3.5 shrink-0 text-[var(--color-fg-faint)] transition-colors group-hover:text-[var(--color-fg-subtle)]" />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1">
        {mock && <MockBadge label={mock} />}
        <TierChip tier={fact.tier} />
        <ProvChip prov={fact.provenance} via={via} />
        <PlaneChip plane={fact.plane === "internal" ? "internal" : "external"} />
        {fact.flag && <FlagChip flag={fact.flag} />}
        {fact.source &&
          (placeholderSrc ? (
            <span
              className="ml-0.5 truncate text-[10.5px] italic text-[var(--color-fg-faint)]"
              title="Placeholder citation — not a real reference."
            >
              {fact.source} · placeholder
            </span>
          ) : (
            <span className="ml-0.5 truncate text-[10.5px] text-[var(--color-fg-subtle)]">
              {fact.source}
            </span>
          ))}
      </div>
    </button>
  );
}

function PlaneColumn({
  title,
  subtitle,
  icon,
  accent,
  facts,
  turnId,
  via,
}: {
  title: string;
  subtitle: string;
  icon: React.ReactNode;
  accent: string;
  facts: { fact: Fact; index: number }[];
  turnId: string;
  via?: string;
}) {
  if (!facts.length) return null;
  return (
    <div className="flex-1">
      <div className="mb-2 flex items-center gap-1.5">
        <span className={cn("flex items-center gap-1.5 text-[12px] font-medium", accent)}>
          {icon}
          {title}
        </span>
        <span className="text-[11px] text-[var(--color-fg-subtle)]">
          · {facts.length} {subtitle}
        </span>
      </div>
      <div className="space-y-1.5">
        {facts.map(({ fact, index }) => (
          <FactCard key={index} fact={fact} index={index} turnId={turnId} via={via} />
        ))}
      </div>
    </div>
  );
}

export function Dossier({ result, turnId }: { result: RunResult; turnId: string }) {
  const dossier = result.discover?.dossier ?? [];
  const via = result._via === "replay" || result._replay ? "replay" : undefined;
  if (!dossier.length) return null;

  const indexed = dossier.map((fact, index) => ({ fact, index }));
  const internal = indexed.filter((x) => x.fact.plane === "internal");
  const external = indexed.filter((x) => x.fact.plane !== "internal");

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)]/40 p-3">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
          Cited fact dossier
        </div>
        <div className="flex items-center gap-2 text-[11px] text-[var(--color-fg-subtle)]">
          <span className="flex items-center gap-1 text-[var(--color-internal)]">
            <Lock className="size-2.5" /> {internal.length}
          </span>
          <span className="flex items-center gap-1 text-[var(--color-external)]">
            <Globe className="size-2.5" /> {external.length}
          </span>
        </div>
      </div>
      <div className="flex flex-col gap-4 lg:flex-row lg:gap-5">
        <PlaneColumn
          title="Internal moat"
          subtitle="private"
          icon={<Lock className="size-3" />}
          accent="text-[var(--color-internal)]"
          facts={internal}
          turnId={turnId}
          via={via}
        />
        {internal.length > 0 && external.length > 0 && (
          <div className="hidden w-px shrink-0 bg-[var(--color-border)] lg:block" />
        )}
        <PlaneColumn
          title="External evidence"
          subtitle="public"
          icon={<Globe className="size-3" />}
          accent="text-[var(--color-external)]"
          facts={external}
          turnId={turnId}
          via={via}
        />
      </div>
    </div>
  );
}
