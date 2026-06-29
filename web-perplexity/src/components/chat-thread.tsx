"use client";
import * as React from "react";
import { AlertCircle, FlaskConical, Activity } from "lucide-react";
import { useFirm, type Turn } from "@/lib/store";
import { agentLabel } from "@/lib/utils";
import { buildSources } from "@/lib/citations";
import type { ProgressEvent } from "@/lib/types";
import { EmptyState } from "@/components/empty-state";
import { Synthesis } from "@/components/run/synthesis";
import { Flags } from "@/components/run/flags";
import { Dossier } from "@/components/run/dossier";
import { Spread } from "@/components/run/spread";
import { Sources } from "@/components/run/sources";

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
  tone: "sim" | "partial" | "error";
  children: React.ReactNode;
}) {
  const style =
    tone === "sim"
      ? "border-[#fcd34d] bg-[var(--color-warn-bg)] text-[var(--color-warn)]"
      : tone === "error"
        ? "border-[#fca5a5] bg-[var(--color-danger-bg)] text-[var(--color-danger)]"
        : "border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-[var(--color-fg-muted)]";
  return (
    <div
      className={`flex items-start gap-2 rounded-[var(--radius)] border px-3 py-2 text-[12px] leading-snug ${style}`}
    >
      {tone === "error" && <AlertCircle className="mt-0.5 size-3.5 shrink-0" />}
      {tone === "sim" && <FlaskConical className="mt-0.5 size-3.5 shrink-0" />}
      <span>{children}</span>
    </div>
  );
}

/** A Perplexity-style firm status bar — the answer's at-a-glance summary. */
function FirmStatusBar({ turn }: { turn: Turn }) {
  const r = turn.result;
  const setInspectorOpen = useFirm((s) => s.setInspectorOpen);
  const setInspectorTab = useFirm((s) => s.setInspectorTab);
  if (!r) return null;

  const agents = r.discover?.agents?.length ?? 0;
  const facts = r.discover?.dossier?.length ?? 0;
  const veto = r.discover?.flags?.VETO?.length ?? 0;
  const div = r.discover?.flags?.DIVERGENCE?.length ?? 0;
  const round = r.consult?.round2?.length ? r.consult.round2 : (r.consult?.round1 ?? []);
  const verdicts = round.length;

  return (
    <div className="flex items-center gap-2.5 rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2">
      <span className="size-[7px] shrink-0 rounded-full bg-[var(--color-ok)] live-dot" />
      <div className="flex-1 text-[11.5px] leading-snug text-[var(--color-fg-muted)]">
        <span className="font-semibold text-[var(--color-fg)]">
          {agents} agent{agents === 1 ? "" : "s"} completed.
        </span>{" "}
        {facts} cited fact{facts === 1 ? "" : "s"}
        {veto ? ` · ${veto} VETO` : ""}
        {div ? ` · ${div} DIVERGENCE` : ""}
        {verdicts ? ` · ${verdicts} verdict${verdicts === 1 ? "" : "s"}` : ""}
      </div>
      <button
        onClick={() => {
          setInspectorTab("monitor");
          setInspectorOpen(true);
        }}
        className="flex shrink-0 items-center gap-1 rounded-[4px] border border-[var(--color-external-border)] bg-[var(--color-external-bg)] px-2 py-1 text-[11px] font-medium text-[var(--color-accent)] transition-colors hover:bg-[var(--color-accent-soft)]"
      >
        <Activity className="size-3" />
        View trace
      </button>
    </div>
  );
}

function TurnView({ turn }: { turn: Turn }) {
  const result = turn.result;
  const status = result?.discover?.status ?? "";
  const ku = result?.discover?.flags?.KNOWN_UNKNOWNS?.length ?? 0;
  const sources = React.useMemo(() => buildSources(result), [result]);

  return (
    <div className="space-y-3.5">
      {/* user query — Perplexity question heading */}
      <div>
        <h2 className="text-[19px] font-semibold leading-snug tracking-tight text-[var(--color-fg)]">
          {turn.query}
        </h2>
      </div>

      {/* firm response */}
      <div className="space-y-3.5 fadeup">
        {turn.status === "running" && !result && <TypingIndicator trace={turn.trace} />}

        {turn.status === "error" && (
          <Banner tone="error">
            The firm could not be convened ({turn.error || "unknown error"}). No answer is
            fabricated.
          </Banner>
        )}

        {result && <FirmStatusBar turn={turn} />}

        {result?._simulated && (
          <Banner tone="sim">
            <b>Simulated-models run.</b> Real moat, EMET PMIDs, seams and Q-Models — but the
            roundtable verdicts and any claude fact-agent reasoning are <b>simulated</b>{" "}
            (labeled <code className="font-mono">simulated</code>), not real model output.
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
            <Synthesis result={result} sources={sources} turnId={turn.id} />
            <Flags flags={result.discover?.flags} />
            <Dossier result={result} sources={sources} turnId={turn.id} />
            <Spread result={result} turnId={turn.id} />
            <Sources sources={sources} turnId={turn.id} />
          </>
        )}
      </div>
    </div>
  );
}

export function ChatThread() {
  const turns = useFirm((s) => s.turns);
  const scrollRef = React.useRef<HTMLDivElement>(null);

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
      <div className="mx-auto max-w-[820px] space-y-8 px-5 py-6">
        {turns.map((t) => (
          <TurnView key={t.id} turn={t} />
        ))}
      </div>
    </div>
  );
}
