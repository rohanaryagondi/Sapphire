"use client";
import * as React from "react";
import { AlertCircle, FlaskConical } from "lucide-react";
import { useFirm, type Turn } from "@/lib/store";
import { agentLabel } from "@/lib/utils";
import type { ProgressEvent } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { Synthesis } from "@/components/run/synthesis";
import { Flags } from "@/components/run/flags";
import { Dossier } from "@/components/run/dossier";
import { Spread } from "@/components/run/spread";

function liveLabel(ev?: ProgressEvent): string {
  if (!ev) return "convening the firm…";
  switch (ev.stage) {
    case "plan":
      return "scoping the engagement…";
    case "bucket1":
      return `gathering facts — ${agentLabel(ev.agent_id)}…`;
    case "flags":
      return "checking VETO / DIVERGENCE…";
    case "roundtable":
      return `roundtable — ${ev.agent_id || "partner"}…`;
    case "synthesis":
      return "writing the synthesis…";
    default:
      return "convening the firm…";
  }
}

function TypingIndicator({ trace }: { trace: ProgressEvent[] }) {
  const last = trace[trace.length - 1];
  return (
    <div className="flex items-center gap-2.5 rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-panel)] px-3 py-2.5">
      <span className="flex items-center gap-1">
        <span className="typedot h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" />
        <span className="typedot h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" />
        <span className="typedot h-1.5 w-1.5 rounded-full bg-[var(--color-accent)]" />
      </span>
      <span className="text-[12.5px] text-[var(--color-fg-muted)]">{liveLabel(last)}</span>
    </div>
  );
}

function Banner({
  tone,
  children,
}: {
  tone: "sim" | "mock" | "partial" | "error";
  children: React.ReactNode;
}) {
  const style =
    tone === "sim" || tone === "mock"
      ? "border-[rgba(210,153,34,0.30)] bg-[rgba(210,153,34,0.06)] text-[#e3b341]"
      : tone === "error"
        ? "border-[rgba(248,81,73,0.30)] bg-[rgba(248,81,73,0.06)] text-[#ff7b72]"
        : "border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-[var(--color-fg-muted)]";
  return (
    <div
      className={`flex items-start gap-2 rounded-[var(--radius)] border px-3 py-2 text-[12px] leading-snug ${style}`}
    >
      {tone === "error" && <AlertCircle className="mt-0.5 size-3.5 shrink-0" />}
      {(tone === "sim" || tone === "mock") && (
        <FlaskConical className="mt-0.5 size-3.5 shrink-0" />
      )}
      <span>{children}</span>
    </div>
  );
}

/** A Demo/mock/generic-fallback run is illustrative, not a real analysis. */
function isMockRun(turn: Turn): boolean {
  const r = turn.result;
  if (!r) return false;
  if (r._simulated) return false; // the simulate banner already covers this
  const via = String(turn.via ?? r._via ?? "").toLowerCase();
  return turn.profile === "demo" || r._mock === true || /fallback|canned|mock/.test(via);
}

function TurnView({ turn }: { turn: Turn }) {
  const result = turn.result;
  const status = result?.discover?.status ?? "";
  const ku = result?.discover?.flags?.KNOWN_UNKNOWNS?.length ?? 0;
  const setMonitorTurn = useFirm((s) => s.setMonitorTurn);
  const setPanelTab = useFirm((s) => s.setPanelTab);
  const setPanelOpen = useFirm((s) => s.setPanelOpen);
  const select = useFirm((s) => s.select);

  /** Open the panel to the Trace tab. */
  const openTrace = () => { setPanelOpen(true); setPanelTab("trace"); };
  /** WO-8 Phase 3: there's no separate whole-dossier view anymore (facts live
   *  inside each step's Info) — this deep link now opens Info on the FIRST
   *  cited dossier fact (a useful "show me a fact" entry point) rather than
   *  landing on an empty Info pane with no selection. */
  const openDossier = () => {
    if (!result?.discover?.dossier?.length) return;
    setPanelOpen(true);
    select({ kind: "fact", index: 0, turnId: turn.id });
  };

  return (
    <div className="space-y-3">
      {/* user query — click to focus this turn's trace in the Monitor (#10) */}
      <div className="flex justify-end">
        <button
          onClick={() => setMonitorTurn(turn.id)}
          title="Show this turn's trace in the Monitor"
          className="max-w-[80%] rounded-[var(--radius-lg)] rounded-br-[4px] border border-[var(--color-border)] bg-[var(--color-elevated)] px-3.5 py-2 text-left text-[13.5px] leading-relaxed text-[var(--color-fg)] transition-colors hover:border-[var(--color-border-focus)]"
        >
          {turn.query}
        </button>
      </div>

      {/* firm response */}
      <div className="space-y-3 fadeup">
        {turn.status === "running" && !result && <TypingIndicator trace={turn.trace} />}

        {/* Deep-link refs — appear once the run is underway / complete */}
        {(turn.status === "running" || result) && (
          <div className="flex items-center gap-2 text-[12px] text-[var(--color-fg-muted)]">
            <span>Full receipts on the right:</span>
            <button
              onClick={openTrace}
              className="rounded-[4px] border border-[var(--color-accent-ring)] bg-[var(--color-accent-soft)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]/80"
            >
              trace ↗
            </button>
            {result && (
              <button
                onClick={openDossier}
                className="rounded-[4px] border border-[var(--color-accent-ring)] bg-[var(--color-accent-soft)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]/80"
              >
                dossier ↗
              </button>
            )}
          </div>
        )}

        {turn.status === "error" && (
          <Banner tone="error">
            The firm could not be convened ({turn.error || "unknown error"}). No answer is
            fabricated.
          </Banner>
        )}

        {isMockRun(turn) && (
          <Banner tone="mock">
            <b>Illustrative mock output.</b> This is canned/Demo-profile data, not a
            real analysis — facts may be placeholders. Switch to the{" "}
            <b>Simulate</b> profile for real moat / EMET / seam data.
          </Banner>
        )}

        {result?._simulated && (
          <Banner tone="sim">
            <b>Simulated-models run.</b> Real moat, EMET PMIDs, seams and Q-Models — but the
            roundtable verdicts and any claude fact-agent reasoning are{" "}
            <b>simulated</b> (labeled <code className="font-mono">simulated</code>), not real
            model output.
          </Banner>
        )}

        {result && status && status !== "complete" && (
          <Banner tone="partial">
            Partial run — status: {status}
            {ku ? ` · ${ku} known-unknown${ku > 1 ? "s" : ""}` : ""}
          </Banner>
        )}

        {result && (
          <>
            <Synthesis result={result} />
            <Flags flags={result.discover?.flags} />
            <Dossier result={result} turnId={turn.id} />
            <Spread result={result} turnId={turn.id} />
          </>
        )}
      </div>
    </div>
  );
}

export function ChatThread() {
  const turns = useFirm((s) => s.turns);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  // auto-scroll to bottom as turns/traces grow
  const lastTraceLen = turns.reduce((n, t) => n + t.trace.length, 0);
  React.useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [turns.length, lastTraceLen]);

  if (turns.length === 0) {
    return (
      <div className="relative flex-1 overflow-hidden">
        <EmptyState />
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto">
      <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
        {turns.map((t) => (
          <TurnView key={t.id} turn={t} />
        ))}
      </div>
    </div>
  );
}
