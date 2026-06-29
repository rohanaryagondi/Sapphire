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
  ModelChoice,
  OpenEvent,
  Profile,
  ProgressEvent,
  RunResult,
} from "./types";

export interface RunRequest {
  query: string;
  profile: Profile;
  model: ModelChoice;
  conversation_id?: string;
  scenario?: string;
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
    }),
    signal: cb.signal,
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`HTTP ${resp.status}`);
  }
  await consumeSSE(resp.body, cb);
}

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

export async function getConversation(id: string): Promise<Conversation | null> {
  try {
    const resp = await fetch(`/api/conversations/${encodeURIComponent(id)}`, {
      method: "GET",
    });
    if (!resp.ok) return null;
    return (await safeJSON(resp)) as Conversation | null;
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
