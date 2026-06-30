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
  /** per-agent fact count, persisted by the engine (absent on older saved runs) */
  n_facts?: number;
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
export type TraceStage = "plan" | "bucket1" | "flags" | "roundtable" | "synthesis" | "redispatch";
export type TracePhase = "start" | "done" | "rebuttal_start" | "rebuttal_done";

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

/** One numbered step in the plan narrative (5 canonical steps). */
export interface PlanStep {
  /** Canonical step key: moat | external | veto | roundtable | synth */
  key: string;
  title: string;
  /** Data plane: "internal" (Quiver moat), "external" (cited), or absent (cross-cutting). */
  plane?: "internal" | "external";
  /** Short badge labels rendered as chips (e.g. ["internal", "moat-real"], ["fda-memory ⛔"]). */
  badges?: string[];
  prose: string;
  /** Expected finding — rendered in a callout box. */
  expect?: string;
  /** What is being skipped and why — rendered in a callout box. */
  skipping?: string;
  /** Optional sub-bullets (agent labels or sub-tasks). */
  sub?: string[];
}

/** Narrated plan — framing paragraph + 5 canonical timeline steps.
 *  Added in Phase B; absent on older/degraded envelopes → card degrades gracefully. */
export interface PlanNarrative {
  framing: string;
  steps: PlanStep[];
}

export interface PlanEnvelope {
  query: string;
  plan?: Plan;
  agents: PlanAgent[];
  plan_source?: string;
  plan_pending_approval?: boolean;
  /** Narrated plan (Phase B). Optional — absent on older envelopes; card degrades. */
  narrative?: PlanNarrative;
  engagement_id?: string;
  _via?: string;
  _bridge_error?: string;
}

/* ── top-bar selectors ──────────────────────────────────────────────────────── */
export type Profile = "demo" | "simulate" | "live" | "replay";
export type ModelChoice = "default" | "sonnet" | "haiku";
