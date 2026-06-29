"use client";
import { FlaskConical, Sparkles } from "lucide-react";
import type { RunResult } from "@/lib/types";
import { cn } from "@/lib/utils";

function confTone(conf: string): string {
  const c = conf.toLowerCase();
  if (/high|strong/.test(c)) return "text-[var(--color-ok)]";
  if (/low|weak/.test(c)) return "text-[var(--color-warn)]";
  return "text-[var(--color-fg-muted)]";
}

export function Synthesis({ result }: { result: RunResult }) {
  const s = result.synthesize;
  if (!s) return null;
  return (
    <div className="relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-gradient-to-b from-[rgba(77,141,255,0.06)] to-[var(--color-panel)] p-4 shadow-[0_1px_0_rgba(255,255,255,0.03),0_18px_40px_-24px_rgba(77,141,255,0.4)]">
      <div className="pointer-events-none absolute -right-12 -top-12 h-32 w-32 rounded-full bg-[radial-gradient(circle,rgba(77,141,255,0.18),transparent_70%)]" />
      <div className="relative">
        <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.08em] text-[var(--color-accent)]">
          <Sparkles className="size-3" />
          Synthesis — the recommendation
        </div>
        <p className="text-[15px] font-medium leading-relaxed text-[var(--color-fg)]">
          {s.recommendation || "—"}
        </p>
        <div className="mt-2.5 flex items-center gap-1.5 text-[12px]">
          <span className="text-[var(--color-fg-subtle)]">Confidence</span>
          <span className={cn("font-semibold", confTone(s.confidence || ""))}>
            {s.confidence || "—"}
          </span>
        </div>

        {s.proposed_experiment && (
          <div className="mt-3 rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-3">
            <div className="mb-1 flex items-center gap-1.5 text-[10.5px] font-medium uppercase tracking-[0.06em] text-[var(--color-fg-subtle)]">
              <FlaskConical className="size-3" />
              Proposed experiment
            </div>
            <p className="text-[13px] leading-relaxed text-[var(--color-fg-muted)]">
              {s.proposed_experiment}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
