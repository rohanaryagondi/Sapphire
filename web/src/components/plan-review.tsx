"use client";
import * as React from "react";
import { Check, ChevronDown, ChevronRight, ClipboardList, Play, ShieldAlert, Wrench, X } from "lucide-react";
import { useFirm } from "@/lib/store";
import { agentLabel, cn, isVetoAgent } from "@/lib/utils";
import { Button } from "@/components/ui/button";

/* A single scientific tool row in the tool-editing panel. */
function ToolRow({
  id,
  name,
  purpose,
  rationale,
  checked,
  onToggle,
}: {
  id: string;
  name: string;
  purpose: string;
  rationale?: string;
  checked: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      aria-pressed={checked}
      data-tool-id={id}
      title={rationale || purpose}
      className={cn(
        "flex w-full items-start gap-2.5 rounded-[var(--radius-sm)] px-2 py-1.5 text-left transition-colors hover:bg-[var(--color-elevated)]",
        !checked && "opacity-45",
      )}
    >
      <span
        className={cn(
          "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-[4px] border",
          checked
            ? "border-[var(--color-accent)] bg-[var(--color-accent)] text-white"
            : "border-[var(--color-border-strong)] bg-transparent",
        )}
      >
        {checked && <Check className="size-3" strokeWidth={3} />}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[12px] font-medium text-[var(--color-fg)]">{name}</span>
        {rationale ? (
          <span className="mt-0.5 block text-[11px] leading-snug text-[var(--color-fg-subtle)]">
            {rationale}
          </span>
        ) : (
          <span className="mt-0.5 block truncate text-[11px] leading-snug text-[var(--color-fg-faint)]">
            {purpose}
          </span>
        )}
      </span>
    </button>
  );
}

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
  const toggleTool = useFirm((s) => s.togglePlanTool);
  const toolsOverride = useFirm((s) => s.toolsOverride);

  // Tool section collapsed state (collapsed by default to keep the card compact).
  const [toolsOpen, setToolsOpen] = React.useState(false);

  // #8 — veto-class agents (FDA Institutional Memory, Patent/IP) gate the
  // roundtable. Warn (dismissibly) whenever one is currently deselected.
  const deselectedVeto = (plan?.agents ?? [])
    .filter((a) => isVetoAgent(a.id) && !a.selected)
    .map((a) => a.id);
  const vetoKey = deselectedVeto.join(",");
  const [vetoDismissed, setVetoDismissed] = React.useState(false);
  const prevVetoKey = React.useRef(vetoKey);
  React.useEffect(() => {
    // re-surface the warning whenever the set of deselected veto agents changes
    if (prevVetoKey.current !== vetoKey) {
      prevVetoKey.current = vetoKey;
      if (vetoKey) setVetoDismissed(false);
    }
  }, [vetoKey]);

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

  // Compute effective tool selection for rendering: user edits win; else backend's list.
  const effectiveToolIds: string[] = toolsOverride ?? plan.tools_selected ?? [];
  const toolsAvailable = plan.tools_available ?? [];
  // Split tools into selected vs available-to-add groups.
  const toolsSelected = toolsAvailable.filter((t) => effectiveToolIds.includes(t.id));
  const toolsDeselected = toolsAvailable.filter((t) => !effectiveToolIds.includes(t.id));
  const hasTools = toolsAvailable.length > 0;
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
                title={a.why || a.role || agentLabel(a.id)}
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
                      <ShieldAlert className="size-3 text-[var(--color-danger)]" />
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

        {/* Scientific tools section — collapsible; only shown when backend emits tools_available */}
        {hasTools && (
          <div className="border-t border-[var(--color-border)]">
            <button
              onClick={() => setToolsOpen((v) => !v)}
              className="flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-[var(--color-elevated)]"
              aria-expanded={toolsOpen}
            >
              {toolsOpen ? (
                <ChevronDown className="size-3 shrink-0 text-[var(--color-fg-subtle)]" />
              ) : (
                <ChevronRight className="size-3 shrink-0 text-[var(--color-fg-subtle)]" />
              )}
              <Wrench className="size-3 shrink-0 text-[var(--color-fg-subtle)]" />
              <span className="text-[11px] font-medium text-[var(--color-fg-muted)]">
                Scientific tools
              </span>
              <span className="ml-1 text-[10.5px] text-[var(--color-fg-faint)]">
                {toolsSelected.length}/{toolsAvailable.length} selected
              </span>
              {toolsOverride !== null && (
                <span className="ml-auto text-[10px] text-[var(--color-accent)]">edited</span>
              )}
            </button>
            {toolsOpen && (
              <div className="max-h-[28vh] overflow-y-auto px-2.5 pb-2">
                {toolsSelected.length > 0 && (
                  <div className="mb-1 px-1.5 pt-1">
                    <span className="text-[10px] uppercase tracking-[0.07em] text-[var(--color-fg-faint)]">
                      Selected
                    </span>
                  </div>
                )}
                {toolsSelected.map((t) => (
                  <ToolRow
                    key={t.id}
                    id={t.id}
                    name={t.name}
                    purpose={t.purpose}
                    rationale={plan.tool_rationale?.[t.id]}
                    checked={true}
                    onToggle={() => toggleTool(t.id)}
                  />
                ))}
                {toolsDeselected.length > 0 && (
                  <div className="mb-1 px-1.5 pt-2">
                    <span className="text-[10px] uppercase tracking-[0.07em] text-[var(--color-fg-faint)]">
                      Available to add
                    </span>
                  </div>
                )}
                {toolsDeselected.map((t) => (
                  <ToolRow
                    key={t.id}
                    id={t.id}
                    name={t.name}
                    purpose={t.purpose}
                    rationale={plan.tool_rationale?.[t.id]}
                    checked={false}
                    onToggle={() => toggleTool(t.id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* #8 — veto-class deselection warning (dismissible) */}
        {deselectedVeto.length > 0 && !vetoDismissed && (
          <div className="flex items-start gap-2 border-t border-[rgba(248,81,73,0.25)] bg-[rgba(248,81,73,0.06)] px-4 py-2.5">
            <ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-[#ff7b72]" />
            <div className="min-w-0 flex-1 text-[11.5px] leading-snug text-[#ff7b72]">
              <b>Veto-class agent deselected.</b>{" "}
              {deselectedVeto.map((id) => agentLabel(id)).join(" · ")} gate{" "}
              {deselectedVeto.length > 1 ? "" : "s"} the roundtable (FDA institutional
              memory / IP). Dropping {deselectedVeto.length > 1 ? "them" : "it"} means the
              partners can't adjudicate that veto.
            </div>
            <button
              onClick={() => setVetoDismissed(true)}
              aria-label="Dismiss warning"
              className="flex size-5 shrink-0 items-center justify-center rounded-[4px] text-[#ff7b72] hover:bg-[rgba(248,81,73,0.12)]"
            >
              <X className="size-3" />
            </button>
          </div>
        )}

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
