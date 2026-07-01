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
  /** the Bucket-1 agent id that contributed this fact (WO-8 Phase 3, stamped
   *  unconditionally by live_engine on every dossier fact); absent on very old
   *  captured scenarios. */
  agent_id?: string;
}

export interface AgentStatus {
  id: string;
  status: string;
  provenance: string;
  /** per-agent fact count, persisted by the engine (absent on older saved runs) */
  n_facts?: number;
  /** actual backend/model that ran (e.g. "claude-haiku-4-5", "EMET / BenchSci", "simulated") */
  model?: string;
  /** concise public-identifier scoped target the agent operated on (e.g. "SCN10A · neuropathic pain") */
  agent_query?: string;
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
  /* round-2 rebuttal deltas (engine emits these on the round-2 entry) */
  revised?: boolean;
  shift?: string;
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
  report?: string;  // Claude-synthesized Markdown diligence report (WO-8 Phase 4)
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
  _model?: string;
  _simulated?: boolean;
  _replay?: boolean;
  _elapsed_s?: number;
  plan_source?: string;
  [k: string]: unknown;
}

/* ── SSE progress event (the live trace) — forwarded verbatim from the engine ── */
export type TraceStage = "plan" | "bucket1" | "flags" | "roundtable" | "synthesis" | "redispatch" | "report";
export type TracePhase = "start" | "done" | "rebuttal_start" | "rebuttal_done" | "chunk";

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
  // round-2 rebuttal fields
  rebuttal_conviction?: number;
  revised?: boolean;
  round?: number;
  /** Per-step takeaway (<=18 words) stamped by the engine summarizer on done events */
  summary?: string;
  /** Actual backend/model that ran for this agent (stamped on done events) */
  model?: string;
  /** Concise public-identifier scoped target the agent operated on */
  agent_query?: string;
  /** report streaming (stage:"report", phase:"chunk") — one accumulated text delta */
  text?: string;
  [k: string]: unknown;
}

export interface OpenEvent {
  profile: string;
  query: string;
  via: string;
}

/* ── persistence: a saved conversation (sibling backend contract) ───────────── */
/* The LIST item shape — GET /api/conversations → { conversations: Conversation[] }. */
export interface Conversation {
  id: string;
  title: string;
  preview?: string;
  starred?: boolean;
  created_at?: string;
  updated_at?: string;
  [k: string]: unknown;
}

/* A persisted message (GET /api/conversations/<id> → messages[]). */
export interface ConversationMessage {
  id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  created_at?: string;
}

/* A persisted RUN — one saved firm convening. The server enriches each run with the
   parsed `result` (the full run_live dict the SSE result frame carried) so the client can
   restore the fully-rendered turn. `result` is absent only if the row's JSON failed to load. */
export interface ConversationRun {
  id: string;
  message_id?: string | null;
  query: string;
  via?: string;
  created_at?: string;
  result?: RunResult | null;
}

/* The DETAIL shape — GET /api/conversations/<id> → { conversation, messages, runs }. */
export interface ConversationDetail {
  conversation: Conversation;
  messages: ConversationMessage[];
  runs: ConversationRun[];
}

/* ── plan mode: the proposed Bucket-1 plan (POST /api/run?mode=plan) ─────────── */
export interface PlanAgent {
  id: string;
  role?: string;
  why?: string;
  selected: boolean;
}

export interface PlanEnvelope {
  query: string;
  plan?: Plan;
  agents: PlanAgent[];
  plan_source?: string;
  plan_pending_approval?: boolean;
  engagement_id?: string;
  _via?: string;
  _bridge_error?: string;
}

/* ── top-bar selectors ──────────────────────────────────────────────────────── */
export type Profile = "demo" | "simulate" | "live" | "replay";
export type ModelChoice = "default" | "sonnet" | "haiku";

/* ── WO-9 Phase 1: main-chat follow-up over a run's stored evidence ─────────── */
/* POST /api/followup response shape (sapphire-orchestrator/followup.py's contract,
   plus the persistence ids the server attaches). */
export interface FollowupResult {
  answer: string;
  citations: string[];
  needs_new_data: boolean;
  missing_agent: string | null;
  source_run_id: string;
  conversation_id: string;
}
