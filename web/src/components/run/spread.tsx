"use client";
import { Users } from "lucide-react";
import type { RunResult, Verdict } from "@/lib/types";
import { cn, stanceKind, stripEmoji } from "@/lib/utils";
import { finalVerdicts, isRebuttalRound } from "@/lib/verdicts";
import { useFirm } from "@/lib/store";

const stanceStyle: Record<string, { bar: string; text: string; fill: string }> = {
  advance: {
    bar: "bg-[var(--color-ok)]",
    text: "text-[var(--color-ok)]",
    fill: "bg-[var(--color-ok)]",
  },
  caution: {
    bar: "bg-[var(--color-warn)]",
    text: "text-[var(--color-warn)]",
    fill: "bg-[var(--color-warn)]",
  },
  block: {
    bar: "bg-[var(--color-danger)]",
    text: "text-[var(--color-danger)]",
    fill: "bg-[var(--color-danger)]",
  },
  neutral: {
    bar: "bg-[var(--color-fg-subtle)]",
    text: "text-[var(--color-fg-muted)]",
    fill: "bg-[var(--color-fg-subtle)]",
  },
};

function ConvictionBar({ conviction, fill }: { conviction: number; fill: string }) {
  const pct = Math.max(0, Math.min(10, conviction)) / 10;
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-[3px] w-[60px] overflow-hidden rounded-full bg-[var(--color-border)]">
        <div
          className={cn("h-full rounded-full transition-all", fill)}
          style={{ width: `${pct * 100}%` }}
        />
      </div>
      <span className="text-[10.5px] text-[var(--color-fg-subtle)]">{conviction}/10</span>
    </div>
  );
}

function VerdictCard({
  v,
  turnId,
  compact,
}: {
  v: Verdict;
  turnId: string;
  compact?: boolean;
}) {
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
      title="Investigate this partner's verdict"
      className={cn(
        "card-hover relative w-full cursor-pointer overflow-hidden rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-panel)] p-3 pl-3.5 text-left",
        active && "border-[var(--color-border-focus)] bg-[var(--color-panel-raised)]",
      )}
    >
      <span className={cn("absolute inset-y-0 left-0 w-[3px]", st.bar)} />
      <div className="mb-1 flex items-center gap-2">
        <span className="flex-1 truncate text-[13px] font-semibold text-[var(--color-fg)]">
          {stripEmoji(v.persona || "partner")}
        </span>
        {ok && v.stance && (
          <span className={cn("text-[11.5px] font-semibold uppercase tracking-tight", st.text)}>
            {stripEmoji(v.stance)}
          </span>
        )}
        {!ok && (
          <span className="text-[11px] text-[var(--color-fg-subtle)]">abstained</span>
        )}
      </div>

      {v.conviction != null && (
        <div className="mb-1.5">
          <ConvictionBar conviction={v.conviction} fill={st.fill} />
        </div>
      )}

      {v.rationale && (
        <p
          className={cn(
            "text-[12px] leading-snug text-[var(--color-fg-muted)]",
            compact ? "line-clamp-2" : "",
          )}
        >
          {stripEmoji(v.rationale)}
        </p>
      )}
    </button>
  );
}

export function Spread({ result, turnId }: { result: RunResult; turnId: string }) {
  const round = finalVerdicts(result);
  const panelOpen = useFirm((s) => s.panelOpen);
  const label = isRebuttalRound(result)
    ? "round 2 · rebuttal"
    : "round 1 · independent verdicts";
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
          <VerdictCard
            key={`${v.persona}_${i}`}
            v={v}
            turnId={turnId}
            compact={panelOpen}
          />
        ))}
      </div>
    </div>
  );
}
