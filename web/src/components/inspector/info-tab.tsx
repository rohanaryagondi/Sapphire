"use client";
/* ============================================================================
   InfoTab — WO-8 Phase 3. The per-step detail view ("Info"): a violet takeaway
   callout, status/provenance/tier/timing/query, the complete contributed-facts
   list (Bucket-1) or round-evolution + full reasoning + dossier cites (Bucket-2),
   a Pin affordance, and the scoped side-chat mounted at the bottom.

   No separate "Dossier" tab per the locked design — the cited facts live inside
   each step's Info. Reuses FactCard/FactList from dossier-tab.tsx (don't
   reinvent fact rendering) and finalVerdicts from lib/verdicts.ts (the single
   source of truth for the merged round-1/round-2 spread).
   ============================================================================ */
import { useMemo, useState } from "react";
import { MousePointerClick, Pin, ShieldAlert } from "lucide-react";
import type { Turn } from "@/lib/store";
import { useFirm } from "@/lib/store";
import { agentLabel, backendLabel, cn, fmtElapsed, isPlaceholderCitation, isVetoAgent, stripEmoji } from "@/lib/utils";
import { finalVerdicts } from "@/lib/verdicts";
import { buildTrace } from "./trace-model";
import { FactList } from "./dossier-tab";
import { Chip, StatusDot } from "@/components/ui/chips";
import type { Fact } from "@/lib/types";
import { SideChat } from "./side-chat";

function EmptyInfo() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <MousePointerClick className="mb-2 size-5 text-[var(--color-fg-faint)]" />
      <p className="text-[12.5px] text-[var(--color-fg-subtle)]">
        Click any agent or partner in the trace to open its full detail, then ask it
        anything from the chat bar below.
      </p>
    </div>
  );
}

function Takeaway({ text }: { text?: string }) {
  if (!text) return null;
  return (
    <div className="mx-0.5 my-2.5 rounded-[8px] border border-[var(--color-q-bd)] bg-gradient-to-b from-[rgba(139,92,246,0.14)] to-[rgba(139,92,246,0.06)] p-3 text-[13px] leading-relaxed text-[#efeaff]">
      <div className="mb-1 text-[9.5px] font-semibold uppercase tracking-[0.06em] text-[var(--color-q-bright)]">
        takeaway
      </div>
      {text}
    </div>
  );
}

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  if (v == null || v === "") return null;
  return (
    <div className="flex gap-3 border-b border-[var(--color-border)] py-1.5 last:border-0">
      <span className="w-20 shrink-0 font-mono text-[11px] text-[var(--color-fg-subtle)]">{k}</span>
      <span className="min-w-0 flex-1 text-[12.5px] text-[var(--color-fg)]">{v}</span>
    </div>
  );
}

/* Keys already rendered elsewhere in AgentInfo (facts via FactList, provenance/candidate
   via KV) — skipped here so "Full detail" only surfaces the genuinely new drill-down
   fields (e.g. qmodels_tool_id/label/input/health for q-models-runner). */
const DETAIL_SKIP_KEYS = new Set(["facts", "candidate", "provenance"]);

/** Full per-agent output (WO-9 Phase 3) — a public-safe key/value drill-down of
 *  whatever the agent's raw output carried beyond the fields already rendered above.
 *  Renders nothing when there's no detail, or nothing left after skipping the
 *  already-shown keys (e.g. an agent whose only output was facts/candidate/provenance). */
function DetailBlock({ detail }: { detail: Record<string, unknown> }) {
  const entries = Object.entries(detail).filter(([k]) => !DETAIL_SKIP_KEYS.has(k));
  if (!entries.length) return null;
  return (
    <div className="mt-3">
      <div className="mb-1.5 px-0.5 text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
        Full detail
      </div>
      <div className="rounded-[8px] border border-[var(--color-border)] bg-[var(--color-panel)] p-2.5">
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-3 border-b border-[var(--color-border)] py-1.5 last:border-0">
            <span className="w-28 shrink-0 font-mono text-[11px] text-[var(--color-fg-subtle)]">{k}</span>
            <span className="min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-[11.5px] text-[var(--color-fg-muted)]">
              {typeof v === "string" ? v : JSON.stringify(v, null, 2)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function PinButton({ turnId, stepKey, label }: { turnId: string; stepKey: string; label: string }) {
  const pinned = useFirm((s) => s.isStepPinned(turnId, stepKey));
  const toggle = useFirm((s) => s.togglePinStep);
  return (
    <button
      onClick={() => toggle({ turnId, key: stepKey, label })}
      title={pinned ? "Unpin from workspace" : "Pin to workspace"}
      aria-label={pinned ? "Unpin from workspace" : "Pin to workspace"}
      aria-pressed={pinned}
      className={cn(
        "flex size-7 shrink-0 items-center justify-center rounded-[var(--radius-sm)] border transition-colors",
        pinned
          ? "border-[var(--color-q-bd)] bg-[var(--color-q-soft)] text-[var(--color-q-bright)]"
          : "border-[var(--color-border)] text-[var(--color-fg-subtle)] hover:border-[var(--color-border-strong)] hover:text-[var(--color-fg)]",
      )}
    >
      <Pin className="size-3.5" fill={pinned ? "currentColor" : "none"} />
    </button>
  );
}

/* ── Bucket-1 agent step ─────────────────────────────────────────────────── */
function AgentInfo({ turn, agentId }: { turn: Turn; agentId: string }) {
  const result = turn.result;
  const m = useMemo(() => buildTrace(turn.trace), [turn.trace]);
  const row = m.bucket1.find((r) => r.agentId === agentId);
  const ev = row?.ev;
  const agentStatus = result?.discover?.agents?.find((a) => a.id === agentId);
  const status = ev?.status ?? agentStatus?.status ?? (row?.done ? "ok" : "running");

  // The complete contributed-facts list — filtered by the agent_id the engine
  // stamps unconditionally on every dossier fact (WO-8 Phase 3 engine seam).
  // Falls back to the older shared-provenance filter for facts/scenarios
  // captured before this seam landed (honest degrade, not a crash).
  const dossier = result?.discover?.dossier ?? [];
  const byAgentId = dossier.filter((f) => f.agent_id === agentId);
  const prov = agentStatus?.provenance ?? ev?.provenance;
  const facts: Fact[] = byAgentId.length
    ? byAgentId
    : dossier.filter((f) => prov && f.provenance === prov);

  const via = result?._via === "replay" || result?._replay ? "replay" : undefined;
  const takeaway = typeof ev?.summary === "string" ? ev.summary : undefined;

  // Model: prefer the recorded value from agent_statuses (persisted in the run result),
  // fall back to the trace done event, then derive from provenance.
  const agentModel: string = agentStatus?.model ?? ev?.model ?? backendLabel(prov, turn.model);
  // Agent query: prefer recorded value, fall back to the engagement query.
  const agentQuery: string = agentStatus?.agent_query ?? ev?.agent_query ?? turn.query ?? "";

  const [prefill, setPrefill] = useState("");

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="mb-1 flex items-start gap-2">
          <StatusDot
            status={status === "ok" ? "ok" : status === "running" ? "running" : "abstain"}
            className="mt-1.5"
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5">
              <span className="truncate text-[13.5px] font-semibold text-[var(--color-fg)]">
                {agentLabel(agentId)}
              </span>
              {isVetoAgent(agentId) && <ShieldAlert className="size-3 shrink-0 text-[var(--color-danger)]" />}
            </div>
            <div className="truncate font-mono text-[11px] text-[var(--color-fg-faint)]">{agentId}</div>
            <div className="text-[10.5px] text-[var(--color-fg-subtle)]">
              {isVetoAgent(agentId) ? "Bucket 1 · veto-class fact agent" : "Bucket 1 · fact agent"}
            </div>
          </div>
          <PinButton turnId={turn.id} stepKey={agentId} label={agentLabel(agentId)} />
        </div>

        <Takeaway text={takeaway} />

        <div className="my-2">
          <KV
            k="status"
            v={isVetoAgent(agentId) ? `${status} · veto gate` : status}
          />
          <KV
            k="provenance"
            v={prov ?? undefined}
          />
          <KV k="model" v={<span className="font-mono text-[11px] text-[var(--color-fg-muted)]">{agentModel}</span>} />
          <KV k="facts · time" v={`${facts.length} fact${facts.length === 1 ? "" : "s"} · ${fmtElapsed(ev?.elapsed_s)}`} />
          {/* "query" — the scoped target the agent actually operated on (honest,
              from the engine's agent record or the engagement query as fallback). */}
          <KV k="query" v={<span className="font-mono text-[11px] text-[var(--color-fg-muted)]">{agentQuery || "—"}</span>} />
        </div>

        <div className="mt-3">
          <div className="mb-1.5 flex items-center gap-2 px-0.5 text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
            Contributed facts <span className="font-mono normal-case tracking-normal text-[var(--color-fg-faint)]">· {facts.length}</span>
          </div>
          {facts.length > 0 ? (
            <FactList facts={facts} via={via} onAsk={(f) => setPrefill(`About: "${f.value.slice(0, 60)}" — explain this.`)} />
          ) : (
            <p className="px-1 text-[12px] text-[var(--color-fg-faint)]">
              {row?.done ? "No facts in the dossier for this agent." : "Running…"}
            </p>
          )}
        </div>

        {agentStatus?.detail && <DetailBlock detail={agentStatus.detail} />}

        <div className="mt-3 rounded-[8px] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-2.5 text-[11.5px] leading-relaxed text-[var(--color-fg-muted)]">
          <b className="text-[var(--color-fg)]">How this fed the run: </b>
          {facts.length > 0
            ? `contributed ${facts.length} cited fact${facts.length === 1 ? "" : "s"} to the Bucket-1 dossier the roundtable deliberated over.`
            : "no facts reached the dossier from this step."}
        </div>
      </div>

      <SideChat
        scopeLabel={agentLabel(agentId)}
        facts={facts}
        agentId={agentId}
        detail={agentStatus?.detail}
        prefill={prefill}
        onPrefillConsumed={() => setPrefill("")}
      />
    </div>
  );
}

/* ── Bucket-2 partner step ───────────────────────────────────────────────── */
function PartnerInfo({ turn, persona }: { turn: Turn; persona: string }) {
  const result = turn.result;
  const round1 = (result?.consult?.round1 ?? []).find((v) => v.persona === persona);
  const round2 = (result?.consult?.round2 ?? []).find((v) => v.persona === persona);
  const final = finalVerdicts(result).find((v) => v.persona === persona);

  const m = useMemo(() => buildTrace(turn.trace), [turn.trace]);
  const row = m.roundtable.find((r) => r.agentId === persona);
  const ev = row?.ev;

  if (!final && !round1) {
    return (
      <div className="flex h-full flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          <div className="mb-1 text-[13.5px] font-semibold text-[var(--color-fg)]">{persona}</div>
          <KV k="status" v={row?.done ? String(ev?.status ?? "") : "deliberating…"} />
        </div>
        <SideChat scopeLabel={persona} facts={[]} agentId={persona} />
      </div>
    );
  }

  const v = final ?? round1!;
  const ok = v.status === "ok";
  const via = result?._via === "replay" || result?._replay ? "replay" : undefined;
  const takeaway = typeof ev?.summary === "string" ? ev.summary : undefined;
  const factClaims = v.fact_claims ?? [];

  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <div className="mb-1 flex items-start gap-2">
          <StatusDot status={ok ? "ok" : "abstain"} className="mt-1.5" />
          <div className="min-w-0 flex-1">
            <span className="block truncate text-[13.5px] font-semibold text-[var(--color-fg)]">{persona}</span>
            <div className="text-[10.5px] text-[var(--color-fg-subtle)]">Bucket 2 · roundtable partner</div>
          </div>
          <PinButton turnId={turn.id} stepKey={persona} label={persona} />
        </div>

        <Takeaway text={takeaway} />

        <div className="my-2">
          <KV
            k="verdict"
            v={
              ok ? (
                <span className="flex items-center gap-1.5">
                  <span className="text-[12px] font-semibold uppercase">{v.stance}</span>
                  {v.conviction != null && <span className="text-[11px] text-[var(--color-fg-faint)]">· conviction {v.conviction}/5</span>}
                </span>
              ) : (
                <span className="text-[11.5px] text-[var(--color-fg-subtle)]">abstained</span>
              )
            }
          />
          <KV k="provenance" v={v.provenance ?? undefined} />
        </div>

        {(round1 || round2) && (
          <div className="mt-3">
            <div className="mb-1.5 px-0.5 text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
              Round evolution
            </div>
            <div className="space-y-1.5 rounded-[8px] border border-[var(--color-border)] bg-[var(--color-panel)] p-2.5 text-[12px] leading-relaxed text-[var(--color-fg-muted)]">
              {round1 && (
                <div>
                  <span className="font-mono text-[10.5px] text-[var(--color-fg-faint)]">R1</span>{" "}
                  {round1.status === "ok"
                    ? `${round1.stance ?? "—"}${round1.conviction != null ? ` · conviction ${round1.conviction}/5` : ""}${round1.rationale ? ` — ${round1.rationale}` : ""}`
                    : "abstained"}
                </div>
              )}
              {round2 && (
                <div>
                  <span className="font-mono text-[10.5px] text-[var(--color-fg-faint)]">R2</span>{" "}
                  {round2.revised
                    ? `revised${round2.conviction != null ? ` · conviction ${round2.conviction}/5` : ""}${round2.shift ? ` — ${round2.shift}` : ""}`
                    : `held firm${round2.conviction != null ? ` · conviction ${round2.conviction}/5` : ""}`}
                </div>
              )}
            </div>
          </div>
        )}

        {v.rationale && (
          <div className="mt-3">
            <div className="mb-1.5 px-0.5 text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
              Full reasoning
            </div>
            <p className="rounded-[8px] border border-[var(--color-border)] bg-[var(--color-panel)] p-2.5 text-[12.5px] leading-relaxed text-[var(--color-fg-muted)]">
              {v.rationale}
            </p>
          </div>
        )}

        {factClaims.length > 0 && (
          <div className="mt-3">
            <div className="mb-1.5 px-0.5 text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
              Cites from the dossier <span className="font-mono normal-case tracking-normal text-[var(--color-fg-faint)]">· {factClaims.length}</span>
            </div>
            <div className="flex flex-wrap gap-1">
              {factClaims.map((c, i) =>
                isPlaceholderCitation(String(c)) ? (
                  <Chip key={i} className="max-w-full truncate italic opacity-60" title="Placeholder citation — not a real reference.">
                    {String(c)} · placeholder
                  </Chip>
                ) : (
                  <Chip key={i} className="max-w-full truncate">{String(c)}</Chip>
                ),
              )}
            </div>
          </div>
        )}

        <div className="mt-3 rounded-[8px] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-2.5 text-[11.5px] leading-relaxed text-[var(--color-fg-muted)]">
          <b className="text-[var(--color-fg)]">How this fed the run: </b>
          {factClaims.length > 0
            ? `cited ${factClaims.length} dossier fact${factClaims.length === 1 ? "" : "s"} — one of the independent verdicts in the spread (never averaged).`
            : "one of the independent verdicts in the spread (never averaged)."}
        </div>
      </div>

      <SideChat
        scopeLabel={persona}
        facts={dossierFactsForClaims(result?.discover?.dossier ?? [], factClaims)}
        agentId={persona}
      />
    </div>
  );
}

/** A partner's side-chat is scoped to the dossier facts it actually cited
 *  (fact_claims) — never the whole dossier. Falls back to [] (honest empty,
 *  not the full dossier) when fact_claims don't resolve to dossier entries. */
function dossierFactsForClaims(dossier: Fact[], claims: string[]): Fact[] {
  if (!claims.length) return [];
  const set = new Set(claims.map((c) => String(c)));
  return dossier.filter((f) => set.has(f.value) || set.has(f.source));
}

export function InfoTab({ turn }: { turn?: Turn }) {
  const selection = useFirm((s) => s.selection);
  const allTurns = useFirm((s) => s.turns);

  // A follow-up turn carries no agent trace of its own — its per-step detail lives in
  // the SOURCE run turn (the same redirect Monitor does for the trace). Resolve it so
  // clicking a trace row after a follow-up opens the source agent's full detail instead
  // of falling back to the empty placeholder.
  const detailTurn = useMemo(() => {
    if (!turn || turn.kind !== "followup") return turn;
    const sourceId = turn.followup?.sourceRunId;
    if (sourceId) {
      const found = allTurns.find((t) => t.id === sourceId && t.kind !== "followup");
      if (found) return found;
    }
    return [...allTurns].reverse().find((t) => t.id !== turn.id && t.kind !== "followup");
  }, [turn, allTurns]);

  // The selection.turnId may reference the display (follow-up) turn OR the source run
  // turn depending on where the row was clicked — accept either so the detail opens.
  const matches =
    selection.kind !== "none" &&
    (selection.turnId === turn?.id || selection.turnId === detailTurn?.id);
  if (!turn || !detailTurn || !matches) {
    return <EmptyInfo />;
  }

  if (selection.kind === "agent") {
    return <AgentInfo turn={detailTurn} agentId={selection.agentId} />;
  }
  if (selection.kind === "verdict") {
    return <PartnerInfo turn={detailTurn} persona={selection.persona} />;
  }
  if (selection.kind === "fact") {
    const fact = detailTurn.result?.discover?.dossier?.[selection.index];
    if (!fact) return <EmptyInfo />;
    const via = detailTurn.result?._via === "replay" ? "replay" : undefined;
    return (
      <div className="flex h-full flex-col">
        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          <div className="mb-2 text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
            Dossier fact
          </div>
          <FactList facts={[fact]} via={via} />
        </div>
        <SideChat scopeLabel={fact.field || fact.source || "this fact"} facts={[fact]} />
      </div>
    );
  }
  return <EmptyInfo />;
}
