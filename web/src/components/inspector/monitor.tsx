"use client";
import * as React from "react";
import { useState, useMemo, useRef, useEffect, useCallback } from "react";
import { Check, ClipboardList, FlagTriangleRight, Sparkles, TriangleAlert } from "lucide-react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { Turn } from "@/lib/store";
import { useFirm } from "@/lib/store";
import { agentLabel, cn, fmtElapsed, isVetoAgent } from "@/lib/utils";
import { finalVerdicts } from "@/lib/verdicts";
import { PlaneChip, ProvChip } from "@/components/ui/chips";
import { buildTrace, type TraceNode, type TraceRow } from "./trace-model";
import type { Verdict } from "@/lib/types";

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

type RowRegistration = { open: () => void; el: HTMLDivElement | null };

function AgentRow({
  row,
  turn,
  registerRow,
}: {
  row: TraceRow;
  turn?: Turn;
  registerRow?: (id: string, reg: RowRegistration) => void;
}) {
  const [open, setOpen] = useState(false);
  const rowRef = useRef<HTMLDivElement>(null);
  const ev = row.ev;

  // Register this row with the Monitor so the focusRowId effect can open+scroll it.
  useEffect(() => {
    if (!registerRow) return;
    registerRow(row.agentId, {
      open: () => setOpen(true),
      el: rowRef.current,
    });
    return () => registerRow(row.agentId, { open: () => {}, el: null });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [row.agentId, registerRow]);
  const isRT = ev.stage === "roundtable";
  const isVeto = isVetoAgent(row.agentId);

  // Status glyph
  let statusEl: React.ReactNode;
  if (!row.started) {
    statusEl = <span className="spinner opacity-30" />;
  } else if (!row.done) {
    statusEl = <span className="spinner" style={{ color: "var(--color-accent)" }} />;
  } else if (isVeto) {
    statusEl = <span className="text-[9px] text-[var(--color-danger)]">⛔</span>;
  } else {
    const ok = String(ev.status ?? "ok") === "ok";
    statusEl = ok
      ? <Check className="size-3 text-[var(--color-ok)]" />
      : <TriangleAlert className="size-3 text-[var(--color-warn)]" />;
  }

  // Facts for this agent (bucket1 only)
  const agentFacts = useMemo(() => {
    if (isRT || !turn?.result) return [];
    const dossier = turn.result.discover?.dossier ?? [];
    const prov = String(ev.provenance ?? "");
    if (!prov) return dossier.slice(0, 5);
    return dossier.filter((f) => f.provenance === prov || f.provenance?.startsWith(prov));
  }, [isRT, turn, ev.provenance]);

  // Verdict for roundtable
  const verdict = useMemo((): Verdict | null => {
    if (!isRT || !turn?.result) return null;
    const all: Verdict[] = [
      ...(turn.result.consult?.round2 ?? []),
      ...(turn.result.consult?.round1 ?? []),
    ];
    return all.find((v) => v.persona === row.agentId) ?? null;
  }, [isRT, turn, row.agentId]);

  return (
    <div
      ref={rowRef}
      data-agent-row={row.agentId}
      className="mx-0.5 my-1 overflow-hidden rounded-[8px] border border-[var(--color-border)] bg-[var(--color-panel)] transition-colors hover:border-[var(--color-border-strong)]"
      style={open ? { borderColor: "var(--color-border-strong)" } : {}}
    >
      {/* clickable header */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-2.5 py-2 text-left"
      >
        <span className="flex size-[15px] shrink-0 items-center justify-center">
          {statusEl}
        </span>
        <span className="flex-1 min-w-0">
          <span className="block truncate font-mono text-[12.5px] font-medium text-[var(--color-fg)]">
            {isRT ? row.agentId || "partner" : agentLabel(row.agentId)}
          </span>
          {row.done && (
            <span className="block truncate text-[11px] text-[var(--color-fg-subtle)]">
              {isRT
                ? ev.stance || "verdict"
                : ev.n_facts != null
                  ? `${ev.n_facts} fact(s)`
                  : ev.status !== "ok" ? String(ev.status ?? "") : "ran"}
            </span>
          )}
        </span>
        {/* right badges */}
        <span className="flex shrink-0 items-center gap-1">
          {!isRT && agentFacts[0]?.plane && (
            <PlaneChip plane={agentFacts[0].plane === "internal" ? "internal" : "external"} />
          )}
          {ev.provenance && <ProvChip prov={ev.provenance} />}
          {isRT && ev.conviction != null && (
            <span className="font-mono text-[10px] text-[var(--color-fg-muted)]">
              {ev.conviction}/5
            </span>
          )}
          {!isRT && ev.n_facts != null && (
            <span className="font-mono text-[10px] text-[var(--color-fg-muted)]">
              {ev.n_facts}
            </span>
          )}
          {ev.elapsed_s != null && (
            <span className="font-mono text-[10px] text-[var(--color-fg-faint)]">
              {fmtElapsed(ev.elapsed_s)}
            </span>
          )}
        </span>
        {/* chevron */}
        <span
          className="shrink-0 text-[10px] text-[var(--color-fg-faint)] transition-transform duration-150"
          style={{
            transform: open ? "rotate(90deg)" : "none",
            color: open ? "var(--color-accent)" : undefined,
          }}
        >
          ▸
        </span>
      </button>

      {/* expandable detail */}
      <div
        style={{
          maxHeight: open ? "520px" : "0px",
          overflow: "hidden",
          transition: "max-height .2s ease",
        }}
      >
        <div className="border-t border-[var(--color-border)] px-3 pb-3 pt-2 text-[11.5px]">
          {isRT ? (
            <>
              {(verdict?.rationale || ev.rationale) && (
                <p className="mb-2 leading-snug text-[var(--color-fg-muted)]">
                  {verdict?.rationale || String(ev.rationale ?? "")}
                </p>
              )}
              <div className="flex flex-wrap gap-1">
                {ev.provenance && <ProvChip prov={ev.provenance} />}
                {ev.conviction != null && (
                  <span className="text-[10.5px] text-[var(--color-fg-faint)]">
                    conviction {ev.conviction}/5
                  </span>
                )}
                {(verdict?.revised || ev.revised) && (
                  <span className="text-[10px] text-[var(--color-warn)]">revised r2</span>
                )}
              </div>
            </>
          ) : (
            agentFacts.length > 0 ? (
              agentFacts.slice(0, 10).map((f, i) => (
                <div
                  key={i}
                  className="flex gap-2 border-b border-[var(--color-border)] py-1.5 last:border-0"
                >
                  <span className="shrink-0 text-[var(--color-fg-faint)]">›</span>
                  <div className="min-w-0">
                    <span className="leading-snug text-[var(--color-fg-muted)]">{f.value}</span>
                    {f.source && (
                      <div className="mt-0.5 font-mono text-[10px] text-[var(--color-external)]">
                        {f.source}
                      </div>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-[var(--color-fg-faint)]">
                {row.done ? "No facts in dossier for this agent." : "Running…"}
              </p>
            )
          )}
        </div>
      </div>
    </div>
  );
}

function AgentList({
  rows,
  turn,
  registerRow,
  outerScrollRef,
}: {
  rows: TraceRow[];
  turn?: Turn;
  registerRow?: (id: string, reg: RowRegistration) => void;
  outerScrollRef?: React.RefObject<HTMLDivElement | null>;
}) {
  const shouldVirtualize = rows.length > 20;
  const virtualizer = useVirtualizer({
    count: rows.length,
    // Use the outer panel scroll container so there's only one scrollbar.
    getScrollElement: () => outerScrollRef?.current ?? null,
    estimateSize: () => 52,
    enabled: shouldVirtualize,
  });

  if (!shouldVirtualize) {
    return (
      <>
        {rows.map((row) => (
          <AgentRow key={row.agentId} row={row} turn={turn} registerRow={registerRow} />
        ))}
      </>
    );
  }

  return (
    <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
      {virtualizer.getVirtualItems().map((vi) => (
        <div
          key={vi.key}
          style={{ position: "absolute", top: vi.start, left: 0, right: 0, height: vi.size }}
        >
          <AgentRow row={rows[vi.index]!} turn={turn} registerRow={registerRow} />
        </div>
      ))}
    </div>
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

function TurnSwitcher({ turn }: { turn: Turn }) {
  const turns = useFirm((s) => s.turns);
  const setMonitorTurn = useFirm((s) => s.setMonitorTurn);
  if (turns.length < 2) return null;
  return (
    <div className="mb-2 border-b border-[var(--color-border)] px-1 pb-2.5">
      <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
        Turn trace · {turns.findIndex((t) => t.id === turn.id) + 1}/{turns.length}
      </div>
      <div className="flex flex-wrap gap-1">
        {turns.map((t, i) => {
          const isLast = i === turns.length - 1;
          return (
            <button
              key={t.id}
              onClick={() => setMonitorTurn(isLast ? null : t.id)}
              title={t.query}
              className={cn(
                "max-w-[150px] truncate rounded-[var(--radius-sm)] border px-1.5 py-0.5 text-[10.5px] transition-colors",
                t.id === turn.id
                  ? "border-[var(--color-border-focus)] bg-[var(--color-elevated)] text-[var(--color-fg)]"
                  : "border-[var(--color-border)] text-[var(--color-fg-subtle)] hover:text-[var(--color-fg-muted)]",
              )}
            >
              <span className="font-mono">{i + 1}.</span> {t.query}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function Monitor({ turn, outerScrollRef }: { turn?: Turn; outerScrollRef?: React.RefObject<HTMLDivElement | null> }) {
  // Registry: agentId → { open fn, DOM element }. Updated by each AgentRow on mount.
  const rowRegistry = useRef<Map<string, RowRegistration>>(new Map());
  const registerRow = useCallback((id: string, reg: RowRegistration) => {
    rowRegistry.current.set(id, reg);
  }, []);

  // Deep-link: when focusRowId changes, open the matching row and scroll it into view.
  const focusRowId = useFirm((s) => s.focusRowId);
  const setFocusRowId = useFirm((s) => s.setFocusRowId);
  useEffect(() => {
    if (!focusRowId) return;
    // Brief delay so the row is mounted (if it just appeared via a new SSE event).
    const t = setTimeout(() => {
      const reg = rowRegistry.current.get(focusRowId);
      if (reg) {
        reg.open();
        reg.el?.scrollIntoView({ block: "center", behavior: "smooth" });
      }
      setFocusRowId(null); // consume — reset so the same id can be re-fired
    }, 80);
    return () => clearTimeout(t);
  }, [focusRowId, setFocusRowId]);

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

  // Memoize buildTrace — it iterates the full trace on every call; during a live run
  // the store pushes a new ProgressEvent on every SSE frame, which would re-render Monitor.
  // Keyed to trace.length so we recompute only when a new event arrives.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const m = useMemo(() => buildTrace(turn.trace), [turn.trace.length]);
  const plan = m.plan?.ev;
  const flagsEv = m.flags?.ev;
  const synthEv = m.synthesis?.ev;

  // Once the run has a result, the roundtable rows are derived from the SAME
  // normalised verdicts the spread renders — so the Monitor can never contradict
  // it (e.g. show "conditional · conviction 3" next to a spread "abstained").
  // While still streaming (no result yet), fall back to the live trace rows.
  const verdicts = finalVerdicts(turn.result);
  const roundtable: TraceRow[] =
    turn.result && verdicts.length
      ? verdicts.map((v) => ({
          agentId: v.persona,
          started: true,
          done: true,
          ev: {
            stage: "roundtable",
            phase: "done",
            agent_id: v.persona,
            status: v.status,
            stance: v.stance,
            conviction: v.conviction,
            provenance: v.provenance,
          },
        }))
      : m.roundtable;
  const rtDone = roundtable.filter((r) => r.done).length;

  return (
    <div className="space-y-1 p-3">
      <TurnSwitcher turn={turn} />
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
          <AgentList rows={m.bucket1} turn={turn} registerRow={registerRow} outerScrollRef={outerScrollRef} />
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

      {roundtable.length > 0 && (
        <div>
          <GroupHeader
            label="Bucket 2 — the roundtable spread"
            done={rtDone}
            total={roundtable.length}
          />
          <AgentList rows={roundtable} turn={turn} registerRow={registerRow} outerScrollRef={outerScrollRef} />
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
