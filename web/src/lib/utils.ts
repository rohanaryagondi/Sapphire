import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/* ── provenance honesty class ─────────────────────────────────────────────────
   Derive a marker class from a fact/agent provenance string — verbatim, never
   relabeled. ● REAL / 🧪 simulated / ◆ CAPTURED. Mirrors frontend2/app.js. */
export type ProvKind = "real" | "sim" | "cap";

export function provKind(prov?: string, via?: string): ProvKind {
  const p = String(prov ?? "").toLowerCase();
  if (p === "simulated") return "sim";
  if (via === "replay" || p === "captured") return "cap";
  if (p === "mock") return "sim";
  return "real";
}

export function provMarker(kind: ProvKind): string {
  return kind === "sim" ? "🧪" : kind === "cap" ? "◆" : "●";
}

export function tierClass(tier?: string): string {
  const t = String(tier ?? "").toUpperCase();
  return t === "T1" || t === "T2" || t === "T3" ? t : "";
}

export function stanceKind(stance?: string): "advance" | "caution" | "block" | "neutral" {
  const s = String(stance ?? "").toLowerCase();
  if (/advance|go|support|favou?r|positive|proceed|yes/.test(s)) return "advance";
  if (/block|veto|reject|no-go|against|kill|stop/.test(s)) return "block";
  if (/caution|hold|conditional|mixed|concern|defer|wait/.test(s)) return "caution";
  return "neutral";
}

/* ── human labels for the ~22 fact agents + control nodes ─────────────────────
   Extends frontend2/app.js AGENT_LABEL with the broader semantic roster. */
export const AGENT_LABEL: Record<string, string> = {
  "internal-science-lead": "Internal moat — Quiver CNS_DFP",
  "emet-runner": "EMET — live BenchSci",
  "emet-analyst": "EMET analyst",
  "q-models-runner": "Q-Models launchpad",
  "fda-institutional-memory": "FDA institutional memory",
  "patent-ip": "Patent / IP",
  "global-regulatory-divergence": "Global regulatory divergence",
  "dea-scheduling": "DEA scheduling",
  "clinical-trial-registry": "Clinical-trial registry",
  "post-market-safety": "Post-market safety",
  "payer": "Payer / reimbursement",
  "financial": "Financial",
  "manufacturing-cmc": "Manufacturing / CMC",
  "patient-advocacy": "Patient advocacy",
  "kol-social": "KOL / social",
  "policy-legislative": "Policy / legislative",
  "reputational": "Reputational",
  "aso-tox": "ASO acute-tox screen",
  "boltz": "Boltz structure / binding",
  "gnomad-constraint": "gnomAD constraint",
  "gtex-expression": "GTEx expression",
  "interpro-domains": "InterPro domains",
  "geneset-enrichment": "g:Profiler enrichment",
  "robyn-scs": "robyn_scs connectivity",
};

/* agents that carry a hard veto gate */
export const VETO_AGENTS = new Set(["fda-institutional-memory", "patent-ip"]);

export function agentLabel(id?: string): string {
  if (!id) return "agent";
  return AGENT_LABEL[id] ?? id;
}

export function isVetoAgent(id?: string): boolean {
  return !!id && VETO_AGENTS.has(id);
}

/* ── time / misc ──────────────────────────────────────────────────────────── */
export function fmtElapsed(s?: number): string {
  if (s == null) return "";
  if (s < 1) return `${Math.round(s * 1000)}ms`;
  return `${s.toFixed(s < 10 ? 1 : 0)}s`;
}

export function relTime(iso?: string): string {
  if (!iso) return "";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "";
  const diff = Date.now() - t;
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}
