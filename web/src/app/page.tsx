"use client";
import { TopBar } from "@/components/topbar";
import { HistoryRail } from "@/components/history-rail";
import { ChatThread } from "@/components/chat-thread";
import { PlanReview } from "@/components/plan-review";
import { Composer } from "@/components/composer";
import { Inspector } from "@/components/inspector";
import { CommandPalette } from "@/components/command-palette";
import { useFirm } from "@/lib/store";

export default function Home() {
  const railOpen = useFirm((s) => s.railOpen);
  const panelOpen = useFirm((s) => s.panelOpen);
  const panelWide = useFirm((s) => s.panelWide);

  // Compute grid-template-columns
  const railCol = railOpen ? "236px" : "0px";
  const panelCol = !panelOpen ? "0px" : panelWide ? "600px" : "400px";
  const cols = `${railCol} 1fr ${panelCol}`;

  return (
    <div className="relative z-10 flex h-dvh flex-col overflow-hidden">
      <TopBar />

      <div
        className="grid min-h-0 flex-1"
        style={{
          gridTemplateColumns: cols,
          transition: "grid-template-columns .22s ease",
        }}
      >
        {/* left — history rail */}
        <aside className="overflow-hidden border-r border-[var(--color-border)] bg-[var(--color-panel)]/50 flex flex-col min-h-0">
          <HistoryRail />
        </aside>

        {/* center — chat thread + composer */}
        <main className="flex min-w-0 flex-1 flex-col bg-[var(--color-bg)] min-h-0">
          <ChatThread />
          <PlanReview />
          <Composer />
        </main>

        {/* right — inspector panel. Always mounted so the grid .22s column-collapse
            animation slides real content (not an empty box). The aside's overflow:hidden
            clips the content when the column collapses to 0px. */}
        <aside className="overflow-hidden border-l border-[var(--color-border)] bg-[var(--color-panel)]/50 flex flex-col min-h-0">
          <Inspector />
        </aside>
      </div>

      <CommandPalette />
    </div>
  );
}
