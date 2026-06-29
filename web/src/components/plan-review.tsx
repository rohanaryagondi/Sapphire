"use client";
import * as React from "react";
import { Check, ClipboardList, Play, X } from "lucide-react";
import { useFirm } from "@/lib/store";
import { agentLabel, cn, isVetoAgent } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/* The plan-review step (Plan-mode). When the user submits with "Plan first" ON, we fetch
   the proposed Bucket-1 plan (zero agents run) and render it here for review: every selected
   agent + its rationale, each deselectable. Approve & Run dispatches the firm with EXACTLY
   the approved agent ids; Cancel discards. Linear-grade: an explicit review gate, not magic. */
export function PlanReview() {
  const plan = useFirm((s) => s.pendingPlan);
  const loading = useFirm((s) => s.planLoading);
  const error = useFirm((s) => s.planError);
  const toggle = useFirm((s) => s.togglePlanAgent);
  const setAll = useFirm((s) => s.setAllPlanAgents);
  const cancel = useFirm((s) => s.cancelPlan);
  const approve = useFirm((s) => s.approvePlan);

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
  const source = plan.plan_source || "deterministic";
  const sourceLabel =
    source === "llm"
      ? "LLM-pruned plan"
      : source === "approved"
        ? "approved"
        : source === "error"
          ? "plan unavailable"
          : "deterministic plan — every fact agent proposed";

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-1">
      <div className="overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-panel)] shadow-[0_8px_30px_rgba(0,0,0,0.25)] fadeup">
        {/* header */}
        <div className="flex items-center justify-between gap-2 border-b border-[var(--color-border)] px-4 py-2.5">
          <div className="flex items-center gap-2">
            <ClipboardList className="size-3.5 text-[var(--color-accent)]" />
            <span className="text-[12.5px] font-semibold text-[var(--color-fg)]">
              Review the plan
            </span>
            <span className="text-[11px] text-[var(--color-fg-subtle)]">· {sourceLabel}</span>
          </div>
          <button
            onClick={cancel}
            aria-label="Cancel plan"
            className="flex size-6 items-center justify-center rounded-[4px] text-[var(--color-fg-subtle)] hover:bg-[var(--color-elevated)] hover:text-[var(--color-fg)]"
          >
            <X className="size-3.5" />
          </button>
        </div>

        {/* query echo */}
        <div className="border-b border-[var(--color-border)] px-4 py-2">
          <p className="truncate text-[12px] text-[var(--color-fg-muted)]">
            <span className="text-[var(--color-fg-subtle)]">Query · </span>
            {plan.query}
          </p>
        </div>

        {/* agent list */}
        <div className="max-h-[34vh] overflow-y-auto px-2.5 py-2">
          <div className="mb-1 flex items-center justify-between px-1.5">
            <span className="text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
              Bucket 1 · fact agents · {selectedCount}/{plan.agents.length} selected
            </span>
            <div className="flex gap-1.5">
              <button
                onClick={() => setAll(true)}
                className="text-[11px] text-[var(--color-fg-subtle)] hover:text-[var(--color-fg)]"
              >
                All
              </button>
              <span className="text-[var(--color-fg-faint)]">·</span>
              <button
                onClick={() => setAll(false)}
                className="text-[11px] text-[var(--color-fg-subtle)] hover:text-[var(--color-fg)]"
              >
                None
              </button>
            </div>
          </div>
          <div className="space-y-0.5">
            {plan.agents.map((a) => (
              <button
                key={a.id}
                onClick={() => toggle(a.id)}
                aria-pressed={a.selected}
                className={cn(
                  "flex w-full items-start gap-2.5 rounded-[var(--radius-sm)] px-2 py-1.5 text-left transition-colors hover:bg-[var(--color-elevated)]",
                  !a.selected && "opacity-45",
                )}
              >
                <span
                  className={cn(
                    "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-[4px] border",
                    a.selected
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white"
                      : "border-[var(--color-border-strong)] bg-transparent",
                  )}
                >
                  {a.selected && <Check className="size-3" strokeWidth={3} />}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1 text-[12.5px] font-medium text-[var(--color-fg)]">
                    {agentLabel(a.id)}
                    {isVetoAgent(a.id) && (
                      <span title="veto-class agent" className="text-[10px] text-[var(--color-danger)]">
                        ⛔
                      </span>
                    )}
                  </span>
                  {a.why ? (
                    <span className="mt-0.5 block text-[11px] leading-snug text-[var(--color-fg-subtle)]">
                      {a.why}
                    </span>
                  ) : a.role ? (
                    <span className="mt-0.5 block truncate text-[11px] leading-snug text-[var(--color-fg-faint)]">
                      {a.role}
                    </span>
                  ) : null}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* actions */}
        <div className="flex items-center justify-between gap-2 border-t border-[var(--color-border)] px-4 py-2.5">
          <span className="text-[11px] text-[var(--color-fg-faint)]">
            Approve to convene exactly the selected agents.
          </span>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={cancel} className="h-7">
              Cancel
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => approve()}
              disabled={selectedCount === 0}
              className="h-7"
            >
              <Play className="size-3.5" />
              Approve &amp; Run
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
