"use client";
import { useEffect } from "react";
import { TopBar } from "@/components/topbar";
import { HistoryRail } from "@/components/history-rail";
import { ChatThread } from "@/components/chat-thread";
import { PlanReview } from "@/components/plan-review";
import { Composer } from "@/components/composer";
import { Inspector } from "@/components/inspector";
import { CommandPalette } from "@/components/command-palette";
import { ToastContainer } from "@/components/toasts";
import { useFirm } from "@/lib/store";

export default function Home() {
  const railOpen = useFirm((s) => s.railOpen);
  const panelOpen = useFirm((s) => s.panelOpen);
  const panelWide = useFirm((s) => s.panelWide);
  const abortRun = useFirm((s) => s.abortRun);

  // Abort any in-flight SSE run when the page component unmounts (e.g. hot-
  // reload, navigation) so the ReadableStream reader doesn't leak.
  useEffect(() => {
    return () => { abortRun(); };
  }, [abortRun]);

  // Compute grid-template-columns
  const railCol = railOpen ? "272px" : "0px";
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
        <aside className="overflow-hidden border-r border-[var(--color-seam)] bg-[var(--color-side)] flex flex-col min-h-0">
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
        <aside className="overflow-hidden border-l border-[var(--color-seam)] bg-[var(--color-side)] flex flex-col min-h-0">
          <Inspector />
        </aside>
      </div>

      <CommandPalette />
      {/* Phase 5: run notification toasts — mounted at root so they survive navigation */}
      <ToastContainer />
    </div>
  );
}
