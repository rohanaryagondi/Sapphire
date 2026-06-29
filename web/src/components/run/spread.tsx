"use client";
import { Users } from "lucide-react";
import type { RunResult, Verdict } from "@/lib/types";
import { cn, stanceKind } from "@/lib/utils";
import { finalVerdicts, isRebuttalRound } from "@/lib/verdicts";
import { Chip, ProvChip } from "@/components/ui/chips";
import { useFirm } from "@/lib/store";

const stanceStyle: Record<string, { bar: string; text: string }> = {
  advance: { bar: "bg-[var(--color-ok)]", text: "text-[var(--color-ok)]" },
  caution: { bar: "bg-[var(--color-warn)]", text: "text-[var(--color-warn)]" },
  block: { bar: "bg-[var(--color-danger)]", text: "text-[var(--color-danger)]" },
  neutral: { bar: "bg-[var(--color-fg-subtle)]", text: "text-[var(--color-fg-muted)]" },
};

function VerdictCard({ v, turnId, via }: { v: Verdict; turnId: string; via?: string }) {
  const select = useFirm((s) => s.select);
  const selection = useFirm((s) => s.selection);
  const ok = v.status === "ok";
  const kind = ok ? stanceKind(v.stance) : "neutral";
  const st = stanceStyle[kind];
  const active =
    selection.kind === "verdict" &&
    selection.persona === v.persona &&
    selection.turnId === turnId;

  return (
    <button
      onClick={() => select({ kind: "verdict", persona: v.persona, turnId })}
      className={cn(
        "card-hover relative w-full overflow-hidden rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-panel)] p-3 pl-3.5 text-left",
        active && "border-[var(--color-border-focus)] bg-[var(--color-panel-raised)]",
      )}
    >
      <span className={cn("absolute inset-y-0 left-0 w-[3px]", st.bar)} />
      <div className="mb-1 flex items-center gap-2">
        <span className="flex-1 truncate text-[13px] font-semibold text-[var(--color-fg)]">
          {v.persona || "partner"}
        </span>
        {ok && v.stance && (
          <span className={cn("text-[11.5px] font-semibold uppercase tracking-tight", st.text)}>
            {v.stance}
          </span>
        )}
        {!ok && (
          <span className="text-[11px] text-[var(--color-fg-subtle)]">abstained</span>
        )}
      </div>
      {v.rationale && (
        <p className="line-clamp-3 text-[12px] leading-snug text-[var(--color-fg-muted)]">
          {v.rationale}
        </p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-1">
        {v.provenance && <ProvChip prov={v.provenance} via={via} />}
        {ok && v.conviction != null && <Chip>conviction {v.conviction}</Chip>}
        {v.lens && <Chip>{v.lens}</Chip>}
      </div>
    </button>
  );
}

export function Spread({ result, turnId }: { result: RunResult; turnId: string }) {
  const round = finalVerdicts(result);
  const label = isRebuttalRound(result)
    ? "round 2 · rebuttal"
    : "round 1 · independent verdicts";
  const via = result._via === "replay" || result._replay ? "replay" : undefined;
  if (!round.length) return null;

  return (
    <div>
      <div className="mb-2 flex items-center gap-2">
        <span className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
          <Users className="size-3" />
          The spread
        </span>
        <span className="text-[11px] text-[var(--color-fg-subtle)]">
          · {round.length} partner{round.length > 1 ? "s" : ""} · no forced consensus · {label}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        {round.map((v, i) => (
          <VerdictCard key={`${v.persona}_${i}`} v={v} turnId={turnId} via={via} />
        ))}
      </div>
    </div>
  );
}
