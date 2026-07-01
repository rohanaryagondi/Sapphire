/* ============================================================================
   Typed API client for the Sapphire firm server (proxied via next.config rewrites
   to the Python backend). Two concerns:
     1) runFirm()  — POST /api/run and consume the SSE stream (open→progress*→
                     result→done|error), invoking typed callbacks.
     2) persistence — conversation CRUD against the sibling backend contract;
                     every call degrades gracefully (returns a safe default) if
                     the endpoint 404s / the backend isn't running yet.
   ============================================================================ */
import type {
  Conversation,
  ConversationDetail,
  Fact,
  FollowupResult,
  ModelChoice,
  OpenEvent,
  PlanEnvelope,
  Profile,
  ProgressEvent,
  ReinvokeResult,
  RunResult,
} from "./types";

export interface RunRequest {
  query: string;
  profile: Profile;
  model: ModelChoice;
  conversation_id?: string;
  scenario?: string;
  approved_plan?: string[];
  /** User-edited tool selection (tool ids) replacing the orchestrator's automatic
   *  selection. When present, the backend's run_live() honours this list instead
   *  of re-running tool_selector. Absent/undefined = use backend selection as-is. */
  tools_override?: string[];
}

export interface RunCallbacks {
  onOpen?: (ev: OpenEvent) => void;
  onProgress?: (ev: ProgressEvent) => void;
  onResult?: (result: RunResult) => void;
  onError?: (message: string) => void;
  onDone?: () => void;
  signal?: AbortSignal;
}

/** The model selector maps to a model id the backend understands (or "" = default). */
function modelId(m: ModelChoice): string {
  if (m === "sonnet") return "claude-sonnet-4-5";
  if (m === "haiku") return "claude-haiku-4-5";
  return "";
}

/** POST /api/run and consume the Server-Sent Events stream. */
export async function runFirm(req: RunRequest, cb: RunCallbacks): Promise<void> {
  const resp = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      query: req.query,
      profile: req.profile,
      model: modelId(req.model),
      conversation_id: req.conversation_id,
      scenario: req.scenario,
      approved_plan: req.approved_plan,
      ...(req.tools_override !== undefined ? { tools_override: req.tools_override } : {}),
    }),
    signal: cb.signal,
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`HTTP ${resp.status}`);
  }
  await consumeSSE(resp.body, cb);
}

/** POST /api/run?mode=plan — fetch the PROPOSED Bucket-1 plan (runs zero agents).
 *  Returns a normalised PlanEnvelope, or null on a network/HTTP failure (the caller
 *  degrades to a direct run). */
export async function fetchPlan(
  req: Pick<RunRequest, "query" | "profile" | "model">,
): Promise<PlanEnvelope | null> {
  try {
    const resp = await fetch("/api/run?mode=plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: req.query,
        profile: req.profile,
        model: modelId(req.model),
      }),
    });
    if (!resp.ok) return null;
    const data = (await safeJSON(resp)) as PlanEnvelope | null;
    if (!data || !Array.isArray(data.agents)) return null;
    return data;
  } catch {
    return null;
  }
}

// We use fetch + ReadableStream (NOT EventSource) because:
// EventSource is GET-only and cannot carry a POST body. Our /api/run
// endpoint requires a POST with the query/profile/model payload.
// fetch() gives us full control: POST body, abort signal, and we parse
// the SSE wire format manually in consumeSSE().
async function consumeSSE(body: ReadableStream<Uint8Array>, cb: RunCallbacks) {
  const reader = body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  let gotResult = false;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx: number;
    // SSE frames are separated by a blank line.
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const { event, data } = parseFrame(frame);
      if (!event) continue;
      switch (event) {
        case "open":
          cb.onOpen?.(data as OpenEvent);
          break;
        case "progress":
          cb.onProgress?.(data as ProgressEvent);
          break;
        case "result":
          gotResult = true;
          cb.onResult?.(data as RunResult);
          break;
        case "error":
          cb.onError?.(
            (data && typeof data === "object" && "error" in data
              ? String((data as { error: unknown }).error)
              : "run failed") || "run failed",
          );
          break;
        case "done":
          cb.onDone?.();
          break;
      }
    }
  }
  if (!gotResult) {
    // stream ended without a result frame and without an explicit error
    cb.onDone?.();
  }
}

interface ParsedFrame {
  event: string | null;
  data: unknown;
}

function parseFrame(frame: string): ParsedFrame {
  let event: string | null = null;
  const dataLines: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).replace(/^ /, ""));
  }
  let data: unknown = null;
  if (dataLines.length) {
    const joined = dataLines.join("\n");
    try {
      data = JSON.parse(joined);
    } catch {
      data = joined;
    }
  }
  return { event, data };
}

/** POST /api/step-chat — a scoped side-chat question over ONLY the facts of
 *  one selected step (never the whole dossier). Returns the model's grounded
 *  answer, or an honest fallback string on a backend failure (never throws). */
export async function askScoped(
  question: string,
  facts: Fact[],
  agentId?: string,
  /** WO-9 Phase 3: the selected agent's full public-safe `detail` (AgentStatus.detail),
   *  when available — supplementary per-agent evidence beyond the flattened fact list
   *  (e.g. the specific Q-Models tool id/label/input it ran). The seam already supports
   *  this end-to-end (sapphire-orchestrator/scoped_chat.py::answer_scoped, forwarded by
   *  frontend2/server.py::_serve_step_chat); only sent when the caller has one. */
  detail?: Record<string, unknown> | null,
): Promise<string> {
  try {
    const resp = await fetch("/api/step-chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        facts,
        agent_id: agentId,
        ...(detail ? { detail } : {}),
      }),
    });
    if (!resp.ok) return "Could not reach the side-chat — try again.";
    const data = (await safeJSON(resp)) as { answer?: string } | null;
    return data?.answer || "No answer returned.";
  } catch {
    return "Could not reach the side-chat — try again.";
  }
}

/** POST /api/followup — WO-9 Phase 1: answer a follow-up question in an EXISTING
 *  conversation from its last real run's STORED evidence (no re-convening the
 *  firm). Follows the exact non-SSE JSON-POST pattern fetchPlan() uses: never
 *  throws to the caller — returns null on any network/HTTP failure so the store
 *  can degrade to an honest error turn. */
export async function askFollowup(
  conversationId: string,
  question: string,
): Promise<FollowupResult | null> {
  try {
    const resp = await fetch("/api/followup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, question }),
    });
    if (!resp.ok) return null;
    const data = (await safeJSON(resp)) as FollowupResult | null;
    if (!data || typeof data.answer !== "string") return null;
    return data;
  } catch {
    return null;
  }
}

/** POST /api/reinvoke — WO-9 Phase 5: actually invoke ONE specific Bucket-1 agent
 *  or Q-Models tool (never the full firm, never the roundtable), fold the new
 *  evidence into the conversation, and re-answer `question` from the grown
 *  evidence. Mirrors askFollowup()'s exact pattern: never throws — returns null
 *  on any network/HTTP failure so the caller degrades to an honest error state. */
export async function reinvokeAgent(
  conversationId: string,
  agentId: string,
  question: string,
  refinedQuery?: string,
): Promise<ReinvokeResult | null> {
  try {
    const resp = await fetch("/api/reinvoke", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: conversationId,
        agent_id: agentId,
        question,
        ...(refinedQuery ? { refined_query: refinedQuery } : {}),
      }),
    });
    if (!resp.ok) return null;
    const data = (await safeJSON(resp)) as ReinvokeResult | null;
    if (!data || typeof data.ok !== "boolean") return null;
    return data;
  } catch {
    return null;
  }
}

/* ============================================================================
   Persistence — conversation history. Sibling backend contract:
     GET    /api/conversations            -> { conversations: Conversation[] } | Conversation[]
     POST   /api/conversations            -> Conversation
     GET    /api/conversations/<id>       -> Conversation (may inline turns)
     PATCH  /api/conversations/<id>       -> Conversation
     DELETE /api/conversations/<id>       -> { ok: true }
   Each call swallows 404 / network errors and returns a safe default so the UI
   never crashes when the backend hasn't merged the endpoints.
   ============================================================================ */

export interface PersistenceState {
  available: boolean;
}

async function safeJSON(resp: Response): Promise<unknown> {
  try {
    return await resp.json();
  } catch {
    return null;
  }
}

export async function listConversations(): Promise<{
  conversations: Conversation[];
  available: boolean;
}> {
  try {
    const resp = await fetch("/api/conversations", { method: "GET" });
    if (!resp.ok) return { conversations: [], available: false };
    const data = await safeJSON(resp);
    const list = Array.isArray(data)
      ? data
      : ((data as { conversations?: Conversation[] })?.conversations ?? []);
    return { conversations: list as Conversation[], available: true };
  } catch {
    return { conversations: [], available: false };
  }
}

export async function createConversation(
  partial: Partial<Conversation>,
): Promise<Conversation | null> {
  try {
    const resp = await fetch("/api/conversations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(partial),
    });
    if (!resp.ok) return null;
    return (await safeJSON(resp)) as Conversation | null;
  } catch {
    return null;
  }
}

export async function getConversation(
  id: string,
): Promise<ConversationDetail | null> {
  try {
    const resp = await fetch(`/api/conversations/${encodeURIComponent(id)}`, {
      method: "GET",
    });
    if (!resp.ok) return null;
    return (await safeJSON(resp)) as ConversationDetail | null;
  } catch {
    return null;
  }
}

export async function patchConversation(
  id: string,
  patch: Partial<Conversation>,
): Promise<Conversation | null> {
  try {
    const resp = await fetch(`/api/conversations/${encodeURIComponent(id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!resp.ok) return null;
    return (await safeJSON(resp)) as Conversation | null;
  } catch {
    return null;
  }
}

export async function deleteConversation(id: string): Promise<boolean> {
  try {
    const resp = await fetch(`/api/conversations/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
    return resp.ok;
  } catch {
    return false;
  }
}
