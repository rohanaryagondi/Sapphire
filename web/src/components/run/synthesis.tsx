"use client";
import * as React from "react";
import type { RunResult } from "@/lib/types";
import { cn, stripEmoji } from "@/lib/utils";
import { exportSynthesis } from "@/lib/export-synthesis";
import { MarkdownDoc } from "./markdown";

/**
 * Synthesis -- the full narrative firm report.
 *
 * When result.synthesize.report is present (live run with report.py):
 *   Renders the Claude-synthesized Markdown report via MarkdownDoc.
 *
 * When report is absent (old cached run):
 *   Renders a terse fallback: recommendation + confidence + a note.
 */
export function Synthesis({ result, turnId }: { result: RunResult; turnId?: string }) {
  const s = result.synthesize;
  const [copied, setCopied] = React.useState(false);

  const handleExport = React.useCallback(() => {
    exportSynthesis(result).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  }, [result]);

  if (!s) return null;

  const report = s.report;

  return (
    <div className="space-y-5">
      {/* Export button -- de-emphasized, top-right */}
      <div className="flex justify-end">
        <button
          onClick={handleExport}
          className={cn(
            "text-[11px] transition-colors",
            "text-[var(--color-fg-faint)] hover:text-[var(--color-fg-muted)]",
          )}
          title="Copy full report to clipboard as Markdown"
        >
          {copied ? "Copied!" : "Export"}
        </button>
      </div>

      {report ? (
        /* Full Claude-synthesized narrative report */
        <MarkdownDoc text={report} turnId={turnId} />
      ) : (
        /* Terse fallback for old cached runs */
        <div className="space-y-3">
          {(s.recommendation || s.confidence) && (
            <div>
              {s.recommendation && (
                <p className="text-[15px] font-medium leading-relaxed text-[var(--color-fg)]">
                  {stripEmoji(s.recommendation)}
                </p>
              )}
              {s.confidence && (
                <p className="mt-1 text-[14px] leading-relaxed text-[var(--color-fg-muted)]">
                  Confidence:{" "}
                  <span className="font-medium">{stripEmoji(s.confidence)}</span>.
                </p>
              )}
            </div>
          )}
          <p className="text-[13px] italic text-[var(--color-fg-faint)]">
            Full narrative not available — run again to generate the report.
          </p>
        </div>
      )}
    </div>
  );
}
