"use client";
import { BookText } from "lucide-react";
import { cn } from "@/lib/utils";
import { useFirm } from "@/lib/store";
import { sourceMeta, sourceTitle, type Source } from "@/lib/citations";

/**
 * The numbered source grid — the anchor of the citation-forward design. Every
 * dossier fact appears as a numbered source [n] that the inline citations in
 * the synthesis (and the fact rows) jump to. Clicking opens the inspector.
 */
export function Sources({ sources, turnId }: { sources: Source[]; turnId: string }) {
  const select = useFirm((s) => s.select);
  const selection = useFirm((s) => s.selection);
  if (!sources.length) return null;

  return (
    <div className="mt-6 border-t border-[var(--color-border)] pt-4">
      <div className="mb-3 flex items-center gap-2 text-[12px] font-semibold text-[var(--color-fg-muted)]">
        <BookText className="size-3.5" />
        Sources cited in this analysis
        <span className="ml-auto text-[11px] font-normal text-[var(--color-fg-faint)]">
          {sources.length} {sources.length === 1 ? "reference" : "references"}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        {sources.map((src) => {
          const active =
            selection.kind === "fact" &&
            selection.index === src.index &&
            selection.turnId === turnId;
          const tier = String(src.fact.tier ?? "").toUpperCase();
          return (
            <button
              key={src.num}
              onClick={() => select({ kind: "fact", index: src.index, turnId })}
              className={cn(
                "card-hover flex items-start gap-2.5 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-panel)] p-2.5 text-left",
                active && "!border-[var(--color-accent)] shadow-[0_0_0_2px_var(--color-accent-soft)]",
              )}
            >
              <span
                className={cn(
                  "mt-px font-mono text-[10px] font-bold",
                  src.internal ? "text-[var(--color-internal)]" : "text-[var(--color-accent)]",
                )}
              >
                {src.internal ? `🔒${src.num}` : src.num}
              </span>
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12px] font-medium text-[var(--color-fg)]">
                  {sourceTitle(src.fact)}
                </div>
                {sourceMeta(src.fact) && (
                  <div className="truncate text-[10.5px] text-[var(--color-fg-faint)]">
                    {sourceMeta(src.fact)}
                  </div>
                )}
                <div className="mt-1 flex flex-wrap gap-1">
                  {(tier === "T1" || tier === "T2" || tier === "T3") && (
                    <span
                      className={cn(
                        "rounded-[3px] px-1.5 py-px text-[9px] font-semibold",
                        tier === "T1"
                          ? "bg-[var(--color-ok-bg)] text-[var(--color-ok)]"
                          : tier === "T2"
                            ? "bg-[var(--color-external-bg)] text-[var(--color-external)]"
                            : "bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)]",
                      )}
                    >
                      {tier}
                    </span>
                  )}
                  <span
                    className={cn(
                      "rounded-[3px] px-1.5 py-px text-[9px] font-medium",
                      src.internal
                        ? "bg-[var(--color-internal-bg)] text-[var(--color-internal)]"
                        : "bg-[var(--color-external-bg)] text-[var(--color-external)]",
                    )}
                  >
                    {src.internal ? "🔒 moat" : "🌐 external"}
                  </span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
