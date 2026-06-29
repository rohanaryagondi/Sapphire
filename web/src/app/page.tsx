"use client";
import { TopBar } from "@/components/topbar";
import { HistoryRail } from "@/components/history-rail";
import { ChatThread } from "@/components/chat-thread";
import { PlanReview } from "@/components/plan-review";
import { Composer } from "@/components/composer";
import { Inspector } from "@/components/inspector";
import { CommandPalette } from "@/components/command-palette";
import { useFirm } from "@/lib/store";
import { cn } from "@/lib/utils";

export default function Home() {
  const inspectorOpen = useFirm((s) => s.inspectorOpen);

  return (
    <div className="relative z-10 flex h-dvh flex-col overflow-hidden">
      <TopBar />

      <div className="flex min-h-0 flex-1">
        {/* left — history rail */}
        <aside className="hidden w-[256px] shrink-0 border-r border-[var(--color-border)] bg-[var(--color-panel)]/50 md:flex md:flex-col">
          <HistoryRail />
        </aside>

        {/* center — chat thread + composer */}
        <main className="flex min-w-0 flex-1 flex-col bg-[var(--color-bg)]">
          <ChatThread />
          <PlanReview />
          <Composer />
        </main>

        {/* right — inspector */}
        <aside
          className={cn(
            "hidden shrink-0 border-l border-[var(--color-border)] bg-[var(--color-panel)]/50 transition-[width] duration-200 lg:flex lg:flex-col",
            inspectorOpen ? "w-[360px]" : "w-0 overflow-hidden border-l-0",
          )}
        >
          {inspectorOpen && <Inspector />}
        </aside>
      </div>

      <CommandPalette />
    </div>
  );
}
