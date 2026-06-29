"use client";
import * as React from "react";
import { Check, ClipboardList, FlagTriangleRight, Sparkles, TriangleAlert } from "lucide-react";
import type { Turn } from "@/lib/store";
import { useFirm } from "@/lib/store";
import { agentLabel, cn, fmtElapsed, isVetoAgent } from "@/lib/utils";
import { ProvChip } from "@/components/ui/chips";
import { buildTrace, type TraceNode, type TraceRow } from "./trace-model";

function StatusGlyph({ node }: { node: TraceNode | TraceRow }) {
  if (node.done) {
    const ok = String(node.ev.status ?? "ok") === "ok";
    return ok ? (
      <Check className="size-3 text-[var(--color-ok)]" />
    ) : (
      <TriangleAlert className="size-3 text-[var(--color-warn)]" />
    );
  }
  return <span className="spinner" />;
}

function TopStep({
  node,
  icon,
  title,
  detail,
}: {
  node?: TraceNode;
  icon: React.ReactNode;
  title: string;
  detail?: React.ReactNode;
}) {
  if (!node) return null;
  return (
    <div className="flex items-start gap-2.5 fadein">
      <div className="mt-0.5 flex size-5 items-center justify-center rounded-full border border-[var(--color-border)] bg-[var(--color-elevated)]">
        {node.done ? icon : <span className="spinner" />}
      </div>
      <div className="min-w-0 flex-1 pb-1">
        <div className="text-[12.5px] font-medium text-[var(--color-fg)]">{title}</div>
        {node.done && detail && (
          <div className="mt-0.5 text-[11.5px] leading-snug text-[var(--color-fg-muted)]">
            {detail}
          </div>
        )}
      </div>
    </div>
  );
}

function AgentRow({ row, turnId }: { row: TraceRow; turnId: string }) {
  const select = useFirm((s) => s.select);
  const selection = useFirm((s) => s.selection);
  const ev = row.ev;
  const ok = String(ev.status ?? "ok") === "ok";
  const isRT = ev.stage === "roundtable";
  const active =
    (selection.kind === "agent" &&
      selection.agentId === row.agentId &&
      selection.turnId === turnId) ||
    (selection.kind === "verdict" &&
      selection.persona === row.agentId &&
      selection.turnId === turnId);

  return (
    <button
      onClick={() =>
        select(
          isRT
            ? { kind: "verdict", persona: row.agentId, turnId }
            : { kind: "agent", agentId: row.agentId, turnId },
        )
      }
      className={cn(
        "flex w-full items-center gap-2 rounded-[var(--radius-sm)] px-2 py-1.5 text-left transition-colors hover:bg-[var(--color-elevated)]",
        active && "bg-[var(--color-elevated)] ring-1 ring-[var(--color-border-focus)]",
      )}
    >
      <span className="flex size-4 shrink-0 items-center justify-center">
        <StatusGlyph node={row} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1 truncate text-[12px] text-[var(--color-fg)]">
          {isRT ? row.agentId || "partner" : agentLabel(row.agentId)}
          {isVetoAgent(row.agentId) && (
            <span title="veto-class agent" className="text-[10px] text-[var(--color-danger)]">
              ⛔
            </span>
          )}
        </div>
        {row.done && (
          <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-[var(--color-fg-subtle)]">
            {isRT ? (
              <span>
                {ok ? ev.stance || "verdict" : "abstained"}
                {ok && ev.conviction != null ? ` · conviction ${ev.conviction}` : ""}
              </span>
            ) : (
              <span>{ok ? `${ev.n_facts ?? 0} fact(s)` : ev.status || "abstained"}</span>
            )}
            {ev.provenance && <ProvChip prov={ev.provenance} />}
            {ev.elapsed_s != null && (
              <span className="font-mono text-[10px] text-[var(--color-fg-faint)]">
                {fmtElapsed(ev.elapsed_s)}
              </span>
            )}
          </div>
        )}
      </div>
    </button>
  );
}

function GroupHeader({
  label,
  done,
  total,
}: {
  label: string;
  done: number;
  total: number;
}) {
  return (
    <div className="mb-1 mt-3 flex items-center gap-2 px-1 first:mt-0">
      <span className="text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
        {label}
      </span>
      <span className="h-px flex-1 bg-[var(--color-border)]" />
      <span className="font-mono text-[10px] text-[var(--color-fg-faint)]">
        {done}/{total}
      </span>
    </div>
  );
}

export function Monitor({ turn }: { turn?: Turn }) {
  if (!turn) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center">
        <ClipboardList className="mb-2 size-5 text-[var(--color-fg-faint)]" />
        <p className="text-[12.5px] text-[var(--color-fg-subtle)]">
          The live trace will appear here once you convene the firm.
        </p>
      </div>
    );
  }

  const m = buildTrace(turn.trace);
  const plan = m.plan?.ev;
  const flagsEv = m.flags?.ev;
  const synthEv = m.synthesis?.ev;

  return (
    <div className="space-y-1 p-3">
      <TopStep
        node={m.plan}
        icon={<ClipboardList className="size-3 text-[var(--color-accent)]" />}
        title="Plan — scoping the engagement"
        detail={
          plan
            ? `${plan.disease || "—"} · ${plan.modality || "—"} · ${(plan.agents || []).length} fact agents · ${(plan.panel || []).length} panel`
            : null
        }
      />

      {m.bucket1.length > 0 && (
        <div>
          <GroupHeader
            label="Bucket 1 — cited fact dossier"
            done={m.b1Done}
            total={m.bucket1.length}
          />
          {m.bucket1.map((row) => (
            <AgentRow key={row.agentId} row={row} turnId={turn.id} />
          ))}
        </div>
      )}

      <TopStep
        node={m.flags}
        icon={<FlagTriangleRight className="size-3 text-[var(--color-warn)]" />}
        title="Flags — VETO / DIVERGENCE"
        detail={
          flagsEv ? (
            <span className="flex flex-wrap gap-1.5">
              <span className="text-[var(--color-danger)]">⛔ {flagsEv.n_veto || 0} VETO</span>
              <span className="text-[var(--color-warn)]">
                ⚠ {flagsEv.n_divergence || 0} DIVERGENCE
              </span>
              <span>{flagsEv.n_known_unknowns || 0} known-unknown(s)</span>
            </span>
          ) : null
        }
      />

      {m.roundtable.length > 0 && (
        <div>
          <GroupHeader
            label="Bucket 2 — the roundtable spread"
            done={m.rtDone}
            total={m.roundtable.length}
          />
          {m.roundtable.map((row) => (
            <AgentRow key={row.agentId} row={row} turnId={turn.id} />
          ))}
        </div>
      )}

      <TopStep
        node={m.synthesis}
        icon={<Sparkles className="size-3 text-[var(--color-accent)]" />}
        title="Synthesis — the recommendation"
        detail={
          synthEv
            ? `${synthEv.recommendation || ""} (confidence: ${synthEv.confidence || "—"})`
            : null
        }
      />
    </div>
  );
}
