"use client";
import { useFirm } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Monitor } from "./monitor";
import { Investigate } from "./investigate";

/**
 * The right panel — a Perplexity-style two-tab pane that toggles a compact live
 * Trace timeline (the firm's activity feed) and a component Inspector (the
 * selected agent / fact / persona / source). Store keys stay "monitor" /
 * "investigate"; the UI labels them Trace / Inspector per the concept.
 */
export function RightPanel() {
  const turns = useFirm((s) => s.turns);
  const running = useFirm((s) => s.running);
  const tab = useFirm((s) => s.inspectorTab);
  const setTab = useFirm((s) => s.setInspectorTab);
  const selection = useFirm((s) => s.selection);

  const activeTurn = turns[turns.length - 1];

  return (
    <div className="flex h-full flex-col">
      {/* tab header — underline-style tabs (Perplexity) */}
      <div className="flex h-12 shrink-0 items-stretch border-b border-[var(--color-border)]">
        <TabBtn
          active={tab === "monitor"}
          onClick={() => setTab("monitor")}
          label="Trace"
          live={running}
        />
        <TabBtn
          active={tab === "investigate"}
          onClick={() => setTab("investigate")}
          label="Inspector"
          badge={selection.kind !== "none"}
        />
      </div>

      {/* live shimmer under the header while running */}
      <div className="h-px shrink-0 bg-[var(--color-border)]">
        {running && <div className="streamline h-px" />}
      </div>

      {/* body */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === "monitor" ? (
          <Monitor turn={activeTurn} />
        ) : (
          <Investigate turns={turns} />
        )}
      </div>
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  label,
  live,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
  live?: boolean;
  badge?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative flex flex-1 items-center justify-center gap-1.5 text-[12px] font-semibold transition-colors",
        active
          ? "text-[var(--color-accent)]"
          : "text-[var(--color-fg-subtle)] hover:text-[var(--color-fg-muted)]",
      )}
    >
      {label}
      {live && (
        <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-accent)] live-dot" />
      )}
      {badge && !live && <span className="text-[var(--color-accent)]">•</span>}
      {active && (
        <span className="absolute inset-x-0 bottom-0 h-[2px] bg-[var(--color-accent)]" />
      )}
    </button>
  );
}
