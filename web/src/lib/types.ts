/* ============================================================================
   Types mirroring the authoritative `run_live` contract
   (sapphire-orchestrator/contracts/run_live_schema.py). The Python dict IS the
   API; these types describe what the SSE `result` event carries. Kept additive-
   friendly: extra keys the engine stamps (_via, _mock, _elapsed_s, …) are allowed.
   ============================================================================ */

export type Plane = "internal" | "external";
export type FlagKind = "VETO" | "DIVERGENCE" | "KNOWN_UNKNOWN";

export interface Fact {
  value: string;
  source: string;
  tier: string;
  provenance: string;
  plane?: Plane;
  field?: string;
  confidence?: string;
  flag?: FlagKind;
}

export interface AgentStatus {
  id: string;
  status: string;
  provenance: string;
}

export interface Verdict {
  persona: string;
  stance: string;
  provenance: string;
  status: string;
  conviction?: number;
  rationale?: string;
  fact_claims?: string[];
  lens?: string;
}

export interface Plan {
  deliverable: string;
  disease: string;
  modality: string;
  agents: string[];
  panel: string[];
}

export interface DiscoverFlags {
  VETO: string[];
  DIVERGENCE: string[];
  KNOWN_UNKNOWNS: string[];
}

export interface Discover {
  dossier: Fact[];
  flags: DiscoverFlags;
  status: string;
  agents: AgentStatus[];
}

export interface Consult {
  round1: Verdict[];
  round2?: Verdict[];
  spread?: Record<string, unknown>;
}

export interface Synthesize {
  recommendation: string;
  confidence: string;
  proposed_experiment: string;
  entities: Record<string, unknown>;
}

export interface RunResult {
  query: string;
  plan: Plan;
  priors?: unknown[];
  discover: Discover;
  consult: Consult;
  synthesize: Synthesize;
  engagement_id: string;
  reflection?: { engagement_id: string; written: number; records: unknown[] };
  _via?: string;
  _mock?: boolean;
  _simulated?: boolean;
  _replay?: boolean;
  _elapsed_s?: number;
}

/* ── SSE progress event (the live trace) — forwarded verbatim from the engine ── */
export type TraceStage = "plan" | "bucket1" | "flags" | "roundtable" | "synthesis";
export type TracePhase = "start" | "done";

export interface ProgressEvent {
  stage: TraceStage | string;
  phase: TracePhase | string;
  agent_id?: string;
  status?: string;
  provenance?: string;
  n_facts?: number;
  elapsed_s?: number;
  // plan
  disease?: string;
  modality?: string;
  agents?: string[];
  panel?: string[];
  // flags
  n_veto?: number;
  n_divergence?: number;
  n_known_unknowns?: number;
  // synthesis
  recommendation?: string;
  confidence?: string;
  // roundtable
  stance?: string;
  conviction?: number;
  error?: string;
  [k: string]: unknown;
}

export interface OpenEvent {
  profile: string;
  query: string;
  via: string;
}

/* ── persistence: a saved conversation (sibling backend contract) ───────────── */
export interface Conversation {
  id: string;
  title: string;
  preview?: string;
  starred?: boolean;
  created_at?: string;
  updated_at?: string;
  // a full conversation (GET /api/conversations/<id>) may inline its turns
  turns?: ConversationTurn[];
  [k: string]: unknown;
}

export interface ConversationTurn {
  query: string;
  profile?: string;
  model?: string;
  result?: RunResult;
  trace?: ProgressEvent[];
}

/* ── top-bar selectors ──────────────────────────────────────────────────────── */
export type Profile = "demo" | "simulate" | "live" | "replay";
export type ModelChoice = "default" | "sonnet" | "haiku";
