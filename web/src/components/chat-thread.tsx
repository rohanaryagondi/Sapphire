"use client";
import * as React from "react";
import { AlertCircle } from "lucide-react";
import { useFirm, type Turn } from "@/lib/store";
import { agentLabel, fmtElapsed, stripEmoji } from "@/lib/utils";
import type { ProgressEvent } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { Synthesis } from "@/components/run/synthesis";
import { Flags } from "@/components/run/flags";
import { Dossier } from "@/components/run/dossier";
import { MarkdownDoc } from "@/components/run/markdown";
import { Button } from "@/components/ui/button";

function liveLabel(ev?: ProgressEvent): string {
  if (!ev) return "convening the firm…";
  switch (ev.stage) {
    case "plan":
      return "scoping the engagement…";
    case "bucket1":
      return `gathering facts -- ${agentLabel(ev.agent_id)}…`;
    case "flags":
      return "checking VETO / DIVERGENCE…";
    case "roundtable":
      return `roundtable -- ${ev.agent_id || "partner"}…`;
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

/** Inline trace pill shown after a run completes. */
function TracePill({ turn }: { turn: Turn }) {
  const setPanelOpen = useFirm((s) => s.setPanelOpen);
  const setPanelTab = useFirm((s) => s.setPanelTab);
  const result = turn.result;

  const nAgents = result?.discover?.agents?.length ?? 0;
  const nFacts = result?.discover?.dossier?.length ?? 0;
  const nPartners = result?.consult?.round1?.length ?? 0;
  const elapsed = fmtElapsed(result?._elapsed_s);

  const handleClick = () => {
    setPanelOpen(true);
    setPanelTab("trace");
  };

  const parts = [
    `Convened the firm`,
    nAgents ? `${nAgents} agents` : null,
    nFacts ? `${nFacts} facts` : null,
    nPartners ? `${nPartners} partners` : null,
    elapsed ? elapsed : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <button
      onClick={handleClick}
      className="inline-flex items-center gap-1 rounded-full border border-[var(--color-border)] bg-[var(--color-panel)] px-3 py-1.5 text-[12px] text-[var(--color-fg-muted)] transition-colors hover:border-[var(--color-border-focus)] cursor-pointer"
    >
      {parts}
      {" "}
      <span className="text-[var(--color-accent)]">show work</span>
    </button>
  );
}

/** Follow-up question chips seeded from synthesize.entities.follow_up_questions. */
function FollowUpChips({ questions }: { questions: string[] }) {
  if (!questions.length) return null;

  const handleClick = (q: string) => {
    // Seed the composer exactly like the empty-state suggestions do (same event
    // + detail shape as components/empty-state.tsx's `fill()`) — this keeps
    // follow-up chips on the SAME single routing path (composer -> `ask()`,
    // WO-9 Phase 1) instead of a second, divergent submission code path.
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent<string>("sapphire:fill", { detail: q }));
    }
  };

  return (
    <div className="flex flex-wrap gap-1.5">
      {questions.map((q, i) => (
        <button
          key={i}
          onClick={() => handleClick(q)}
          className="rounded-full border border-[var(--color-q-bd,var(--color-border-focus))] bg-[var(--color-q-soft,var(--color-accent-soft))] px-3 py-1 text-[12px] text-[var(--color-q-text,var(--color-accent))] cursor-pointer transition-colors hover:bg-[rgba(139,92,246,0.18)]"
        >
          {q}
        </button>
      ))}
    </div>
  );
}

/** WO-9 Phase 1: renders a follow-up turn — the answer synthesized from a prior
 *  run's STORED evidence (no re-convened firm). Citation pills come free via
 *  MarkdownDoc's existing [[Label]] parsing. When the model flagged a genuine
 *  evidence gap (needsNewData), an explicit escalation affordance is shown —
 *  the full firm is only ever convened on a deliberate user click, never
 *  silently/automatically. */
function FollowupAnswer({ turn }: { turn: Turn }) {
  const submit = useFirm((s) => s.submit);
  const f = turn.followup;

  if (turn.status === "running") {
    return <TypingIndicator trace={[]} />;
  }

  if (turn.status === "error" || !f) {
    return (
      <Banner tone="error">
        {turn.error || "Could not answer from this run's evidence. No answer is fabricated."}
      </Banner>
    );
  }

  return (
    <div className="space-y-3 fadeup">
      <div className="rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-panel)] px-4 py-3">
        <MarkdownDoc text={f.answer} turnId={turn.id} />
      </div>
      {f.needsNewData && (
        <div className="flex flex-col gap-2 rounded-[var(--radius)] border border-[rgba(210,153,34,0.30)] bg-[rgba(210,153,34,0.06)] px-3 py-2.5 text-[12px] text-[#e3b341]">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 size-3.5 shrink-0" />
            <span>
              This needs data not in this run
              {f.missingAgent ? <> -- from: <b>{f.missingAgent}</b></> : null}.
            </span>
          </div>
          <div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => submit(turn.query)}
            >
              Run the full firm on this
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export function TurnView({ turn }: { turn: Turn }) {
  const result = turn.result;
  const status = result?.discover?.status ?? "";
  const ku = result?.discover?.flags?.KNOWN_UNKNOWNS?.length ?? 0;
  const setPanelOpen = useFirm((s) => s.setPanelOpen);
  const setPanelTab = useFirm((s) => s.setPanelTab);
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

  const followUpQuestions: string[] = (() => {
    const entities = result?.synthesize?.entities as Record<string, unknown> | undefined;
    const raw = entities?.follow_up_questions;
    return Array.isArray(raw) ? (raw as string[]).filter((x) => typeof x === "string") : [];
  })();

  return (
    <div className="space-y-3">
      {/* user query -- click to focus this turn's trace in the Monitor (#10) */}
      <div className="flex justify-end">
        <button
          onClick={openTrace}
          title="Show this turn's trace in the Monitor"
          className="max-w-[80%] rounded-[var(--radius-lg)] rounded-br-[4px] border border-[var(--color-border)] bg-[var(--color-elevated)] px-3.5 py-2 text-left text-[15px] leading-relaxed text-[var(--color-fg)] transition-colors hover:border-[var(--color-border-focus)]"
        >
          {turn.query}
        </button>
      </div>

      {/* WO-9 Phase 1: a follow-up turn renders the stored-evidence answer, never
          the full-firm response chrome (trace pill, dossier, roundtable, …). */}
      {turn.kind === "followup" ? (
        <FollowupAnswer turn={turn} />
      ) : (
      <div className="space-y-3 fadeup">
        {/* WO-9 Phase 2: once the report starts streaming, replace the generic
            typing indicator with the growing report itself (progressive render --
            no 70-100s spinner). Reuses MarkdownDoc, the same component Synthesis
            uses for the authoritative final report, so there's no rendering-logic
            duplication and no visible flicker once `result` lands. */}
        {turn.status === "running" && !result && (
          turn.streamingReport ? (
            <div className="space-y-2 fadeup">
              <div className="flex items-center gap-1.5 text-[11px] text-[var(--color-fg-subtle)]">
                <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-accent)] live-dot" />
                writing the report…
              </div>
              <MarkdownDoc text={turn.streamingReport} turnId={turn.id} />
            </div>
          ) : (
            <TypingIndicator trace={turn.trace} />
          )
        )}

        {/* Live status: running with or without a partial result */}
        {turn.status === "running" && (
          <div className="flex items-center gap-2 text-[12px] text-[var(--color-fg-muted)]">
            <span>Full receipts on the right:</span>
            <button
              onClick={openTrace}
              className="rounded-[4px] border border-[var(--color-accent-ring)] bg-[var(--color-accent-soft)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]/80"
            >
              trace
            </button>
            {result && (
              <button
                onClick={openDossier}
                className="rounded-[4px] border border-[var(--color-accent-ring)] bg-[var(--color-accent-soft)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]/80"
              >
                dossier
              </button>
            )}
          </div>
        )}

        {/* Complete: inline trace pill */}
        {turn.status === "complete" && result && (
          <TracePill turn={turn} />
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
            real analysis -- facts may be placeholders. Switch to the{" "}
            <b>Simulate</b> profile for real Quiver data / EMET / seam data.
          </Banner>
        )}

        {result?._simulated && (
          <Banner tone="sim">
            <b>Simulated-models run.</b> Real Quiver data, EMET PMIDs, seams and External Models -- but the
            roundtable verdicts and any claude fact-agent reasoning are{" "}
            <b>simulated</b> (labeled <code className="font-mono">simulated</code>), not real
            model output.
          </Banner>
        )}

        {result && status && status !== "complete" && (
          <Banner tone="partial">
            Partial run -- status: {status}
            {ku ? ` · ${ku} known-unknown${ku > 1 ? "s" : ""}` : ""}
          </Banner>
        )}

        {result && (
          <>
            <Synthesis result={result} turnId={turn.id} />
            <Flags flags={result.discover?.flags} />
            <Dossier result={result} turnId={turn.id} />
          </>
        )}

        {/* Follow-up chips -- only shown after complete result */}
        {turn.status === "complete" && followUpQuestions.length > 0 && (
          <FollowUpChips questions={followUpQuestions} />
        )}
      </div>
      )}
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
