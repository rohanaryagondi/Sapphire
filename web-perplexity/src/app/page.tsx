"use client";
import { HistoryRail } from "@/components/history-rail";
import { ChatHeader } from "@/components/chat-header";
import { ChatThread } from "@/components/chat-thread";
import { Composer } from "@/components/composer";
import { RightPanel } from "@/components/inspector";
import { CommandPalette } from "@/components/command-palette";
import { useFirm } from "@/lib/store";
import { cn } from "@/lib/utils";

export default function Home() {
  const inspectorOpen = useFirm((s) => s.inspectorOpen);

  return (
    <div className="flex h-dvh overflow-hidden bg-[var(--color-bg)]">
      {/* left — history rail */}
      <aside className="hidden w-[240px] shrink-0 flex-col border-r border-[var(--color-border)] bg-[var(--color-panel)] md:flex">
        <HistoryRail />
      </aside>

      {/* center — chat header + thread + composer */}
      <main className="flex min-w-0 flex-1 flex-col">
        <ChatHeader />
        <ChatThread />
        <Composer />
      </main>

      {/* right — trace ⇄ inspector */}
      <aside
        className={cn(
          "hidden shrink-0 flex-col border-l border-[var(--color-border)] bg-[var(--color-panel)] transition-[width] duration-200 lg:flex",
          inspectorOpen ? "w-[340px]" : "w-0 overflow-hidden border-l-0",
        )}
      >
        {inspectorOpen && <RightPanel />}
      </aside>

      <CommandPalette />
    </div>
  );
}
