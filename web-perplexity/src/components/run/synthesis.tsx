"use client";
import { FlaskConical, Hexagon } from "lucide-react";
import type { RunResult } from "@/lib/types";
import { cn } from "@/lib/utils";
import { jumpToSource, type Source } from "@/lib/citations";

function confTone(conf: string): string {
  const c = conf.toLowerCase();
  if (/high|strong/.test(c)) return "text-[var(--color-ok)]";
  if (/low|weak/.test(c)) return "text-[var(--color-warn)]";
  return "text-[var(--color-fg-muted)]";
}

/** The inline citation marker — Perplexity's signature element. */
function CiteMarker({
  source,
  turnId,
}: {
  source: Source;
  turnId: string;
}) {
  return (
    <button
      onClick={() => jumpToSource(turnId, source.num)}
      className={cn("cite", source.internal && "cite-internal")}
      title={source.fact.value}
    >
      {source.internal ? `🔒${source.num}` : source.num}
    </button>
  );
}

/**
 * The answer block — Perplexity-style synthesis prose with a first-class
 * citation row. The recommendation is the engine's verbatim text; below it we
 * surface every dossier source as a numbered, clickable citation that jumps to
 * the source grid (honest: a number always resolves to a real cited fact).
 */
export function Synthesis({
  result,
  sources,
  turnId,
}: {
  result: RunResult;
  sources: Source[];
  turnId: string;
}) {
  const s = result.synthesize;
  if (!s) return null;

  return (
    <div className="answer-prose">
      <p className="text-[15px] font-medium leading-[1.7] text-[var(--color-fg)]">
        {s.recommendation || "—"}
        {sources.length > 0 && (
          <span className="ml-0.5 whitespace-nowrap align-super">
            {sources.slice(0, 12).map((src) => (
              <CiteMarker key={src.num} source={src} turnId={turnId} />
            ))}
          </span>
        )}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px]">
        <span className="flex items-center gap-1.5">
          <span className="text-[var(--color-fg-subtle)]">Confidence</span>
          <span className={cn("font-semibold", confTone(s.confidence || ""))}>
            {s.confidence || "—"}
          </span>
        </span>
        {sources.length > 0 && (
          <span className="text-[var(--color-fg-subtle)]">
            Grounded in{" "}
            <span className="font-medium text-[var(--color-fg)]">{sources.length}</span>{" "}
            cited {sources.length === 1 ? "source" : "sources"}
          </span>
        )}
      </div>

      {s.proposed_experiment && (
        <div className="mt-4 rounded-[var(--radius)] border border-[#c7d2fe] bg-gradient-to-br from-[#f0f9ff] to-[var(--color-purple-bg)] p-3.5">
          <div className="mb-1.5 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-[0.06em] text-[var(--color-purple)]">
            <Hexagon className="size-3" />
            Proposed experiment
          </div>
          <div className="flex items-start gap-2">
            <FlaskConical className="mt-0.5 size-3.5 shrink-0 text-[var(--color-purple)]" />
            <p className="text-[13px] leading-relaxed text-[var(--color-fg)]">
              {s.proposed_experiment}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
