"use client";
import * as React from "react";
import { Check, ChevronRight, Play, X } from "lucide-react";
import { useFirm } from "@/lib/store";
import { agentLabel, cn, isVetoAgent } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Chip, FlagChip, MockBadge, PlaneChip, ProvChip } from "@/components/ui/chips";
import type { PlanStep } from "@/lib/types";

/* ── Phase B — Prose plan card (WO-7 Phase B).
   Renders the narrated plan envelope as a timeline card:
     - synthesis-card grammar (blue gradient + glow + accent eyebrow)
     - framing paragraph
     - 5 numbered timeline steps (moat → external → veto → roundtable → synth)
     - badges from chips.tsx (PlaneChip / ProvChip / FlagChip / Chip)
     - expect: / skipping: callout boxes
     - "Edit the agents" disclosure (agent pills, veto agents locked / non-deselectable)
     - Approve & Run button calls approvePlan() — wiring unchanged from Phase A.

   Honesty rules:
     - deterministic / error plans are honestly labeled (MockBadge "templated plan")
     - if narrative is absent, degrade to a minimal honest render from plan fields
     - depth/roundtable controls are OMITTED (no engine channel exists for Phase B;
       only approved_plan: string[] crosses the wire; showing controls that do nothing
       would be dishonest — omit is the correct choice per the brief).
*/

// ── step number chip styling by key ─────────────────────────────────────────
function StepNumChip({ stepKey, num }: { stepKey: string; num: number | string }) {
  const isInternal = stepKey === "moat";
  const isVeto = stepKey === "veto";
  return (
    <div
      className={cn(
        "flex h-6 w-6 flex-none items-center justify-center rounded-[7px] border text-[11px] font-semibold z-[1] font-mono",
        isInternal
          ? "border-[rgba(192,132,252,0.5)] bg-[rgba(192,132,252,0.08)] text-[#d6b4fe]"
          : isVeto
            ? "border-[rgba(248,81,73,0.45)] bg-[rgba(248,81,73,0.07)] text-[#ff7b72]"
            : "border-[var(--color-border-strong)] bg-[var(--color-bg-subtle)] text-[var(--color-fg-muted)]",
      )}
    >
      {num}
    </div>
  );
}

// ── expect / skipping callout box ────────────────────────────────────────────
function Callout({
  label,
  text,
  variant = "expect",
}: {
  label: string;
  text: string;
  variant?: "expect" | "skipping";
}) {
  return (
    <div className="mt-1.5 rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2.5 py-1.5 text-[12px] leading-snug text-[var(--color-fg-subtle)]">
      <span className="mr-1.5 text-[9.5px] font-semibold uppercase tracking-[0.05em] text-[var(--color-fg-faint)]">
        {label}
      </span>
      {text}
    </div>
  );
}

// ── render a single step badge string → chip ─────────────────────────────────
function StepBadge({ badge }: { badge: string }) {
  const b = badge.toLowerCase();
  if (b === "internal") return <PlaneChip plane="internal" />;
  if (b === "external") return <PlaneChip plane="external" />;
  if (b.includes("moat-real") || b.includes("moat_real")) return <ProvChip prov="moat-real" />;
  if (b.startsWith("t1")) return <Chip className="border-[rgba(77,141,255,0.40)] bg-[rgba(77,141,255,0.12)] text-[#9cc1ff]">T1</Chip>;
  if (b.startsWith("t2")) return <Chip className="border-[rgba(125,133,255,0.32)] bg-[rgba(125,133,255,0.10)] text-[#b3b8ff]">T2</Chip>;
  if (b.includes("⛔") || b.includes("veto") || b.includes("fda-memory") || b.includes("patent"))
    return <FlagChip flag="VETO" />;
  // generic labelled chip
  return <Chip>{badge}</Chip>;
}

// ── a single timeline step ───────────────────────────────────────────────────
function TimelineStep({ step, num }: { step: PlanStep; num: number }) {
  const isLast = false; // connector is handled by CSS ::before on parent
  return (
    <div className="flex gap-3 py-3 relative">
      {/* vertical connector line (CSS pseudo-element would need extra wrapper; use border trick) */}
      <div className="flex flex-col items-center gap-0">
        <StepNumChip stepKey={step.key} num={step.key === "veto" ? "⛔" : num} />
        {/* connector — draw as a thin div; last step won't be followed by another, handled below */}
      </div>
      <div className="min-w-0 flex-1 pb-2 border-b border-[var(--color-border)]">
        {/* title + badges */}
        <div className="mb-1 flex flex-wrap items-center gap-1.5">
          <span className="text-[13.5px] font-semibold text-[var(--color-fg)]">{step.title}</span>
          {step.badges?.map((b, i) => (
            <StepBadge key={i} badge={b} />
          ))}
        </div>
        {/* prose */}
        <p className="text-[13px] leading-relaxed text-[var(--color-fg-muted)]">{step.prose}</p>
        {/* sub-bullets */}
        {step.sub && step.sub.length > 0 && (
          <ul className="mt-1.5 flex flex-col gap-1">
            {step.sub.map((s, i) => (
              <li key={i} className="flex gap-2 text-[12.5px] leading-snug text-[var(--color-fg-muted)]">
                <span className="flex-none text-[var(--color-fg-faint)]">›</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        )}
        {/* expect / skipping callouts */}
        {step.expect && <Callout label="expect" text={step.expect} variant="expect" />}
        {step.skipping && <Callout label="skipping" text={step.skipping} variant="skipping" />}
      </div>
    </div>
  );
}

// ── main component ───────────────────────────────────────────────────────────
export function PlanReview() {
  const plan = useFirm((s) => s.pendingPlan);
  const loading = useFirm((s) => s.planLoading);
  const error = useFirm((s) => s.planError);
  const toggle = useFirm((s) => s.togglePlanAgent);
  const setAll = useFirm((s) => s.setAllPlanAgents);
  const cancel = useFirm((s) => s.cancelPlan);
  const approve = useFirm((s) => s.approvePlan);

  const [agentsOpen, setAgentsOpen] = React.useState(false);

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 pb-1">
        <div className="flex items-center gap-2.5 rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-panel)] px-4 py-3">
          <span className="spinner" />
          <span className="text-[12.5px] text-[var(--color-fg-muted)]">
            Drafting the plan — selecting which fact agents to convene…
          </span>
        </div>
      </div>
    );
  }

  if (error && !plan) {
    return (
      <div className="mx-auto w-full max-w-3xl px-4 pb-1">
        <div className="flex items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-[rgba(248,81,73,0.3)] bg-[rgba(248,81,73,0.06)] px-4 py-2.5">
          <span className="text-[12.5px] text-[#ff7b72]">{error}</span>
          <Button variant="ghost" size="sm" onClick={cancel} className="h-7">
            Dismiss
          </Button>
        </div>
      </div>
    );
  }

  if (!plan) return null;

  const selectedCount = plan.agents.filter((a) => a.selected).length;
  const planSource = plan.plan_source ?? "deterministic";
  const isError = planSource === "error";

  // Narrative — present in Phase B envelopes; absent in older/degraded responses.
  const narrative = plan.narrative;
  const hasNarrative = !!(narrative?.framing && narrative?.steps?.length);

  // Honesty label is keyed to narrative.source (the prose author), NOT plan_source
  // (which reflects whether the LLM *selected agents*). A plan where the LLM selected
  // agents but the narrative was built deterministically must still show the label.
  // narrative.source === "llm" → real LLM prose → no label.
  // anything else (undefined / "deterministic") → templated prose → show label.
  const narrativeIsLLM = narrative?.source === "llm";
  const showTemplatedLabel = !narrativeIsLLM;

  // Meta line: N agents selected
  const metaAgents = `${selectedCount} agent${selectedCount !== 1 ? "s" : ""}`;

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-1">
      {/* Synthesis-card grammar: blue gradient + glow + border */}
      <div className="relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-gradient-to-b from-[rgba(77,141,255,0.06)] to-[var(--color-panel)] shadow-[0_1px_0_rgba(255,255,255,0.03),0_18px_44px_-26px_rgba(77,141,255,0.5)] fadeup">
        {/* glow orb */}
        <div className="pointer-events-none absolute -right-12 -top-12 h-[150px] w-[150px] rounded-full bg-[radial-gradient(circle,rgba(77,141,255,0.16),transparent_70%)]" />

        {/* ── header ── */}
        <div className="relative flex items-center gap-2 px-4 pt-4 pb-2">
          {/* accent eyebrow */}
          <span className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--color-accent)]">
            <span>◆</span>
            Plan — how I&apos;ll work this
          </span>
          {/* meta */}
          <span className="ml-auto font-mono text-[11px] text-[var(--color-fg-muted)] tabular-nums">
            diligence · <strong className="text-[var(--color-fg)]">{metaAgents}</strong>
          </span>
          {/* cancel */}
          <button
            onClick={cancel}
            aria-label="Cancel plan"
            className="ml-1 flex h-6 w-6 items-center justify-center rounded-[4px] text-[var(--color-fg-subtle)] hover:bg-[var(--color-elevated)] hover:text-[var(--color-fg)]"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        {/* honesty label when narrative prose is not LLM-authored */}
        {showTemplatedLabel && (
          <div className="relative flex items-center gap-2 px-4 pb-1">
            <MockBadge label={isError ? "MOCK" : "ILLUSTRATIVE"} />
            <span className="text-[11px] text-[var(--color-fg-subtle)]">
              {isError
                ? "plan unavailable — templated fallback"
                : "templated plan — LLM narration not available"}
            </span>
          </div>
        )}

        {/* ── framing paragraph ── */}
        {hasNarrative ? (
          <div className="relative px-4 pb-2">
            <p className="text-[14.5px] font-[450] leading-relaxed text-[var(--color-fg)]">
              {narrative!.framing}
            </p>
          </div>
        ) : (
          /* Degraded render: no narrative — show query + agent count */
          <div className="relative px-4 pb-2">
            <p className="text-[13px] leading-relaxed text-[var(--color-fg-muted)]">
              <span className="font-semibold text-[var(--color-fg)]">Query: </span>
              {plan.query}
            </p>
            <p className="mt-1 text-[12px] text-[var(--color-fg-muted)]">
              {selectedCount} fact agent{selectedCount !== 1 ? "s" : ""} selected.
            </p>
          </div>
        )}

        {/* ── timeline steps ── */}
        {hasNarrative && (
          <div className="relative px-4">
            {/* vertical connector line behind the step chips */}
            <div className="relative">
              {/* draw connector line from first to last step */}
              <div className="absolute left-[11.5px] top-[30px] bottom-[10px] w-px bg-[var(--color-border)]" />
              {narrative!.steps.map((step, i) => {
                const isLastStep = i === narrative!.steps.length - 1;
                return (
                  <div key={step.key} className={cn("relative", isLastStep && "[&_.border-b]:border-b-0")}>
                    <TimelineStep step={step} num={i + 1} />
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Edit the agents disclosure ── */}
        <button
          onClick={() => setAgentsOpen((v) => !v)}
          className={cn(
            "relative flex w-full items-center gap-2 border-t border-[var(--color-border)] px-4 py-2.5 text-[11.5px] text-[var(--color-fg-subtle)] hover:text-[var(--color-fg)] transition-colors",
            agentsOpen && "text-[var(--color-fg)]",
          )}
        >
          <ChevronRight
            className={cn(
              "h-3.5 w-3.5 transition-transform",
              agentsOpen && "rotate-90 text-[var(--color-accent)]",
            )}
          />
          {agentsOpen ? "hide" : "edit"} the {plan.agents.length} agents &amp; gates Sapphire selected
        </button>

        {agentsOpen && (
          <div className="relative border-t border-[var(--color-border)]">
            {/* select-all controls */}
            <div className="flex items-center justify-between px-4 py-1.5">
              <span className="text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
                Bucket 1 · {selectedCount}/{plan.agents.length} selected
              </span>
              <div className="flex gap-1.5 text-[11px] text-[var(--color-fg-subtle)]">
                <button onClick={() => setAll(true)} className="hover:text-[var(--color-fg)]">
                  All
                </button>
                <span className="text-[var(--color-fg-faint)]">·</span>
                <button onClick={() => setAll(false)} className="hover:text-[var(--color-fg)]">
                  None
                </button>
              </div>
            </div>
            {/* agent pills */}
            <div className="flex flex-wrap gap-1.5 px-4 pb-3">
              {plan.agents.map((a) => {
                const veto = isVetoAgent(a.id);
                if (veto) {
                  // Locked veto pills — non-deselectable ⛔
                  return (
                    <span
                      key={a.id}
                      title="Veto-class agent — locked (gates the roundtable)"
                      className="inline-flex cursor-not-allowed items-center gap-1.5 rounded-[7px] border border-[rgba(248,81,73,0.30)] bg-[rgba(248,81,73,0.07)] px-2 py-1 font-mono text-[11.5px] text-[#ff9b94]"
                    >
                      <span className="h-[5px] w-[5px] rounded-full bg-current opacity-80" />
                      {agentLabel(a.id)} ⛔
                    </span>
                  );
                }
                return (
                  <button
                    key={a.id}
                    onClick={() => toggle(a.id)}
                    aria-pressed={a.selected}
                    title={a.why || a.role || agentLabel(a.id)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-[7px] border px-2 py-1 font-mono text-[11.5px] transition-colors cursor-pointer",
                      a.selected
                        ? "border-[rgba(192,132,252,0.30)] bg-[rgba(192,132,252,0.08)] text-[#d6b4fe] hover:bg-[rgba(192,132,252,0.12)]"
                        : "border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-[var(--color-fg-muted)] opacity-60 hover:opacity-100",
                    )}
                  >
                    <span className="h-[5px] w-[5px] rounded-full bg-current opacity-80" />
                    {agentLabel(a.id)}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* ── Approve & Run footer ── */}
        <div className="relative flex items-center gap-3 border-t border-[var(--color-border)] px-4 py-3">
          <Button
            variant="default"
            size="sm"
            onClick={() => approve()}
            disabled={selectedCount === 0}
            className="h-8 gap-1.5"
          >
            <Play className="h-3.5 w-3.5" />
            Approve &amp; Run
          </Button>
          <button
            onClick={cancel}
            className="text-[12px] text-[var(--color-fg-subtle)] hover:text-[var(--color-accent)]"
          >
            or tell me to rethink a step
          </button>
          <span className="ml-auto text-[11px] text-[var(--color-fg-faint)]">
            Approve to convene exactly the selected agents.
          </span>
        </div>
      </div>
    </div>
  );
}
