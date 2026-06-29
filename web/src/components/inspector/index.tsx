"use client";
import { Activity, Search, X } from "lucide-react";
import { useFirm } from "@/lib/store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Monitor } from "./monitor";
import { Investigate } from "./investigate";

export function Inspector() {
  const turns = useFirm((s) => s.turns);
  const running = useFirm((s) => s.running);
  const tab = useFirm((s) => s.inspectorTab);
  const setTab = useFirm((s) => s.setInspectorTab);
  const setOpen = useFirm((s) => s.setInspectorOpen);
  const selection = useFirm((s) => s.selection);

  // monitor follows the most recent turn
  const activeTurn = turns[turns.length - 1];

  return (
    <div className="flex h-full flex-col">
      {/* tab header */}
      <div className="flex h-11 shrink-0 items-center gap-1 border-b border-[var(--color-border)] px-2">
        <TabBtn
          active={tab === "monitor"}
          onClick={() => setTab("monitor")}
          icon={<Activity className="size-3.5" />}
          label="Monitor"
          live={running}
        />
        <TabBtn
          active={tab === "investigate"}
          onClick={() => setTab("investigate")}
          icon={<Search className="size-3.5" />}
          label="Investigate"
          badge={selection.kind !== "none" ? "•" : undefined}
        />
        <div className="flex-1" />
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => setOpen(false)}
          aria-label="Close inspector"
        >
          <X className="size-3.5" />
        </Button>
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
  icon,
  label,
  live,
  badge,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  live?: boolean;
  badge?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "relative flex h-7 items-center gap-1.5 rounded-[var(--radius-sm)] px-2.5 text-[12.5px] font-medium transition-colors",
        active
          ? "bg-[var(--color-elevated)] text-[var(--color-fg)]"
          : "text-[var(--color-fg-subtle)] hover:text-[var(--color-fg-muted)]",
      )}
    >
      {icon}
      {label}
      {live && (
        <span className="ml-0.5 h-1.5 w-1.5 rounded-full bg-[var(--color-accent)] live-dot" />
      )}
      {badge && !live && (
        <span className="ml-0.5 text-[var(--color-accent)]">{badge}</span>
      )}
    </button>
  );
}
