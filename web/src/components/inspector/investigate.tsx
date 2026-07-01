"use client";
import { MousePointerClick, ShieldAlert } from "lucide-react";
import type { Turn } from "@/lib/store";
import { useFirm, type InspectorSelection } from "@/lib/store";
import { agentLabel, backendLabel, cn, fmtElapsed, isPlaceholderCitation, isVetoAgent, mockLabel, stanceKind, stripEmoji } from "@/lib/utils";
import { finalVerdicts } from "@/lib/verdicts";
import { buildTrace } from "./trace-model";
import {
  Chip,
  FlagChip,
  MockBadge,
  StatusDot,
} from "@/components/ui/chips";

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  if (v == null || v === "") return null;
  return (
    <div className="flex gap-3 border-b border-[var(--color-border)] py-1.5 last:border-0">
      <span className="w-24 shrink-0 font-mono text-[11px] text-[var(--color-fg-subtle)]">
        {k}
      </span>
      <span className="min-w-0 flex-1 text-[12.5px] text-[var(--color-fg)]">{v}</span>
    </div>
  );
}

function Header({
  eyebrow,
  title,
  right,
}: {
  eyebrow: React.ReactNode;
  title: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-3 border-b border-[var(--color-border)] pb-3">
      <div className="mb-1 text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
        {eyebrow}
      </div>
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-[14px] font-semibold leading-tight text-[var(--color-fg)]">
          {title}
        </h3>
        {right}
      </div>
    </div>
  );
}

function EmptyInvestigate() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <MousePointerClick className="mb-2 size-5 text-[var(--color-fg-faint)]" />
      <p className="text-[12.5px] text-[var(--color-fg-subtle)]">
        Click any agent, fact, or partner verdict to investigate its detailed output,
        sources, and provenance.
      </p>
    </div>
  );
}

function FactDetail({ turn, index }: { turn: Turn; index: number }) {
  const fact = turn.result?.discover?.dossier?.[index];
  if (!fact) return <EmptyInvestigate />;
  const via = turn.result?._via === "replay" ? "replay" : undefined;
  const mock = mockLabel(fact.provenance, fact.value, fact.source);
  return (
    <div className="p-3.5">
      <Header
        eyebrow={mock ? "Dossier fact · mock/illustrative" : "Dossier fact"}
        title={fact.field || fact.source || "fact"}
      />
      <p
        className={cn(
          "mb-3 rounded-[var(--radius)] border p-2.5 text-[13px] leading-relaxed",
          mock
            ? "border-dashed border-[rgba(210,153,34,0.35)] bg-[var(--color-bg-subtle)]/50 italic text-[var(--color-fg-muted)]"
            : "border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-[var(--color-fg)]",
        )}
      >
        {stripEmoji(fact.value)}
      </p>
      <div className="mb-3 flex flex-wrap gap-1">
        {mock && <MockBadge label={mock} />}
        {fact.flag && <FlagChip flag={fact.flag} />}
      </div>
      <KV
        k="source"
        v={
          fact.source &&
          (isPlaceholderCitation(fact.source) ? (
            <span className="italic text-[var(--color-fg-muted)]">
              {fact.source} · placeholder citation (not a real reference)
            </span>
          ) : (
            fact.source
          ))
        }
      />
      <KV k="field" v={fact.field} />
      <KV k="tier" v={fact.tier} />
      <KV k="provenance" v={fact.provenance} />
      <KV k="plane" v={fact.plane ?? "external"} />
      <KV k="confidence" v={fact.confidence} />
      <KV k="flag" v={fact.flag} />
    </div>
  );
}

function AgentDetail({ turn, agentId }: { turn: Turn; agentId: string }) {
  const result = turn.result;
  const agent = result?.discover?.agents?.find((a) => a.id === agentId);
  const m = buildTrace(turn.trace);
  const row = m.bucket1.find((r) => r.agentId === agentId);
  const ev = row?.ev;
  // facts attributable to this agent by shared provenance (best-effort)
  const prov = agent?.provenance ?? ev?.provenance;
  const facts = (result?.discover?.dossier ?? []).filter(
    (f) => prov && f.provenance === prov,
  );
  const status = agent?.status ?? ev?.status ?? (row?.done ? "ok" : "running");

  return (
    <div className="p-3.5">
      <Header
        eyebrow={
          isVetoAgent(agentId) ? (
            <span className="flex items-center gap-1">Bucket 1 fact agent · veto-class <ShieldAlert className="size-3 text-[var(--color-danger)]" /></span>
          ) : "Bucket 1 fact agent"
        }
        title={agentLabel(agentId)}
        right={
          <span className="flex items-center gap-1.5 text-[11px] text-[var(--color-fg-muted)]">
            <StatusDot status={status === "ok" ? "ok" : status === "running" ? "running" : "abstain"} />
            {status}
          </span>
        }
      />
      <KV k="agent id" v={<span className="font-mono text-[11.5px]">{agentId}</span>} />
      <KV k="status" v={status} />
      <KV k="provenance" v={prov ?? "—"} />
      <KV k="model" v={agent?.model ?? backendLabel(prov, turn.model)} />
      <KV k="query" v={agent?.agent_query ?? turn.query ?? "—"} />
      <KV k="facts" v={ev?.n_facts != null ? `${ev.n_facts}` : `${facts.length}`} />
      <KV k="elapsed" v={ev?.elapsed_s != null ? fmtElapsed(ev.elapsed_s) : undefined} />
      {ev?.error ? <KV k="note" v={String(ev.error)} /> : null}

      {facts.length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
            Contributed facts · {facts.length}
          </div>
          <div className="space-y-1.5">
            {facts.map((f, i) => (
              <div
                key={i}
                className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-panel)] p-2"
              >
                <p className="text-[12px] leading-snug text-[var(--color-fg)]">{f.value}</p>
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {f.flag && <FlagChip flag={f.flag} />}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function VerdictDetail({ turn, persona }: { turn: Turn; persona: string }) {
  const round = finalVerdicts(turn.result);
  const v = round.find((x) => x.persona === persona);
  if (!v) {
    // maybe still running — show trace row
    const m = buildTrace(turn.trace);
    const row = m.roundtable.find((r) => r.agentId === persona);
    return (
      <div className="p-3.5">
        <Header eyebrow="Bucket 2 partner" title={persona} />
        <KV k="status" v={row?.done ? row.ev.status : "deliberating…"} />
      </div>
    );
  }
  const ok = v.status === "ok";
  const kind = ok ? stanceKind(v.stance) : "neutral";
  const tone =
    kind === "advance"
      ? "text-[var(--color-ok)]"
      : kind === "block"
        ? "text-[var(--color-danger)]"
        : kind === "caution"
          ? "text-[var(--color-warn)]"
          : "text-[var(--color-fg-muted)]";
  return (
    <div className="p-3.5">
      <Header
        eyebrow="Bucket 2 partner verdict"
        title={v.persona}
        right={
          ok ? (
            <span className={`text-[12px] font-semibold uppercase ${tone}`}>{v.stance}</span>
          ) : (
            <span className="text-[11px] text-[var(--color-fg-subtle)]">abstained</span>
          )
        }
      />
      {v.rationale && (
        <p className="mb-3 rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] p-2.5 text-[12.5px] leading-relaxed text-[var(--color-fg-muted)]">
          {v.rationale}
        </p>
      )}
      <KV k="stance" v={v.stance} />
      <KV k="conviction" v={v.conviction != null ? String(v.conviction) : undefined} />
      <KV k="lens" v={v.lens} />
      <KV k="provenance" v={v.provenance ?? "—"} />
      <KV k="status" v={v.status} />
      {(v.fact_claims ?? []).length > 0 && (
        <div className="mt-3">
          <div className="mb-1.5 text-[10.5px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
            Cited dossier facts · {v.fact_claims!.length}
          </div>
          <div className="flex flex-wrap gap-1">
            {v.fact_claims!.map((c, i) =>
              isPlaceholderCitation(String(c)) ? (
                <Chip
                  key={i}
                  className="max-w-full truncate italic opacity-60"
                  title="Placeholder citation — not a real reference."
                >
                  {String(c)} · placeholder
                </Chip>
              ) : (
                <Chip key={i} className="max-w-full truncate">
                  {String(c)}
                </Chip>
              ),
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function StepDetail({ turn, stage }: { turn: Turn; stage: string }) {
  const result = turn.result;
  if (stage === "plan" && result?.plan) {
    const p = result.plan;
    return (
      <div className="p-3.5">
        <Header eyebrow="Control step" title="Plan — scoping the engagement" />
        <KV k="deliverable" v={p.deliverable} />
        <KV k="disease" v={p.disease} />
        <KV k="modality" v={p.modality} />
        <KV k="fact agents" v={`${(p.agents ?? []).length}`} />
        <KV k="panel" v={`${(p.panel ?? []).length} partners`} />
      </div>
    );
  }
  if (stage === "synthesis" && result?.synthesize) {
    const s = result.synthesize;
    return (
      <div className="p-3.5">
        <Header eyebrow="Control step" title="Synthesis" />
        <KV k="recommendation" v={s.recommendation} />
        <KV k="confidence" v={s.confidence} />
        <KV k="experiment" v={s.proposed_experiment} />
      </div>
    );
  }
  if (stage === "flags" && result?.discover?.flags) {
    const f = result.discover.flags;
    return (
      <div className="p-3.5">
        <Header eyebrow="Control step" title="Flags — VETO / DIVERGENCE" />
        <KV k="VETO" v={`${(f.VETO ?? []).length}`} />
        <KV k="DIVERGENCE" v={`${(f.DIVERGENCE ?? []).length}`} />
        <KV k="known-unknowns" v={`${(f.KNOWN_UNKNOWNS ?? []).length}`} />
      </div>
    );
  }
  return <EmptyInvestigate />;
}

export function Investigate({ turns }: { turns: Turn[] }) {
  const selection = useFirm((s) => s.selection) as InspectorSelection;
  if (selection.kind === "none") return <EmptyInvestigate />;
  const turn = turns.find((t) => t.id === selection.turnId);
  if (!turn) return <EmptyInvestigate />;

  switch (selection.kind) {
    case "fact":
      return <FactDetail turn={turn} index={selection.index} />;
    case "agent":
      return <AgentDetail turn={turn} agentId={selection.agentId} />;
    case "verdict":
      return <VerdictDetail turn={turn} persona={selection.persona} />;
    case "step":
      return <StepDetail turn={turn} stage={selection.stage} />;
    default:
      return <EmptyInvestigate />;
  }
}
