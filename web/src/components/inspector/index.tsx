"use client";
import { useRef } from "react";
import { Activity } from "lucide-react";
import { useFirm } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Monitor } from "./monitor";
import { DossierTab } from "./dossier-tab";

export function Inspector() {
  const turns = useFirm((s) => s.turns);
  const running = useFirm((s) => s.running);
  const tab = useFirm((s) => s.panelTab);
  const setTab = useFirm((s) => s.setPanelTab);
  const setPanelOpen = useFirm((s) => s.setPanelOpen);
  const setPanelWide = useFirm((s) => s.setPanelWide);
  const panelWide = useFirm((s) => s.panelWide);
  const monitorTurnId = useFirm((s) => s.monitorTurnId);

  // The outer scroll container ref is threaded into Monitor so the virtualizer
  // (and the focusRowId scrollIntoView) uses the panel's single scroll surface,
  // preventing a nested double-scrollbar when > 20 agent rows are rendered.
  const scrollRef = useRef<HTMLDivElement>(null);

  const activeTurn =
    (monitorTurnId && turns.find((t) => t.id === monitorTurnId)) ||
    turns[turns.length - 1];

  return (
    <div className="flex h-full flex-col">
      {/* tab header */}
      <div className="flex h-11 shrink-0 items-center gap-1 border-b border-[var(--color-border)] px-2">
        <button
          onClick={() => setTab("trace")}
          className={cn(
            "relative flex h-7 items-center gap-1.5 rounded-[var(--radius-sm)] px-2.5 text-[12.5px] font-medium transition-colors",
            tab === "trace"
              ? "bg-[var(--color-elevated)] text-[var(--color-fg)]"
              : "text-[var(--color-fg-subtle)] hover:text-[var(--color-fg-muted)]",
          )}
        >
          <Activity className="size-3.5" />
          Trace
          {running && (
            <span className="ml-0.5 h-1.5 w-1.5 rounded-full bg-[var(--color-ok)] live-dot" />
          )}
        </button>
        <button
          onClick={() => setTab("dossier")}
          className={cn(
            "relative flex h-7 items-center gap-1.5 rounded-[var(--radius-sm)] px-2.5 text-[12.5px] font-medium transition-colors",
            tab === "dossier"
              ? "bg-[var(--color-elevated)] text-[var(--color-fg)]"
              : "text-[var(--color-fg-subtle)] hover:text-[var(--color-fg-muted)]",
          )}
        >
          Dossier
          {activeTurn?.result?.discover?.dossier?.length ? (
            <span className="ml-0.5 font-mono text-[10px] text-[var(--color-fg-faint)]">
              {activeTurn.result.discover.dossier.length}
            </span>
          ) : null}
        </button>
        <div className="flex-1" />
        {/* ⤢ widen */}
        <button
          onClick={() => setPanelWide(!panelWide)}
          className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-sm)] text-[13px] text-[var(--color-fg-muted)] transition-colors hover:bg-[var(--color-elevated)] hover:text-[var(--color-fg)]"
          title="Widen panel"
          aria-label="Widen panel"
        >
          ⤢
        </button>
        {/* › close */}
        <button
          onClick={() => setPanelOpen(false)}
          className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-sm)] text-[13px] text-[var(--color-fg-muted)] transition-colors hover:bg-[var(--color-elevated)] hover:text-[var(--color-fg)]"
          title="Hide panel"
          aria-label="Hide panel"
        >
          ›
        </button>
      </div>

      {/* live shimmer */}
      <div className="h-px shrink-0 bg-[var(--color-border)]">
        {running && <div className="streamline h-px" />}
      </div>

      {/* body — single scroll surface; Monitor's virtualizer binds to this ref */}
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        {tab === "trace" ? (
          <Monitor turn={activeTurn} outerScrollRef={scrollRef} />
        ) : (
          <DossierTab turn={activeTurn} />
        )}
      </div>

      {/* hintbar */}
      <div className="shrink-0 border-t border-[var(--color-border)] px-3 py-2 text-[11px] text-[var(--color-fg-faint)]">
        ↳ click any row to expand · ⤢ widen the panel
      </div>
    </div>
  );
}
