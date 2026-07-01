"use client";
/* ============================================================================
   The client-side firm store (Zustand). Owns: top-bar selectors, the active
   conversation thread (turns), the live trace per running turn, the inspector
   selection, and conversation history. Network lives in lib/api.ts; this is
   orchestration + view state only.
   ============================================================================ */
import { create } from "zustand";
import {
  askFollowup as apiAskFollowup,
  createConversation,
  deleteConversation,
  fetchPlan,
  getConversation,
  listConversations,
  patchConversation,
  runFirm,
} from "./api";
import { traceFromResult } from "./restore";
import { exportSynthesis } from "./export-synthesis";
import type {
  Conversation,
  ModelChoice,
  PlanEnvelope,
  ProgressEvent,
  Profile,
  RunResult,
} from "./types";

export type TurnStatus = "running" | "complete" | "error";

// ── Phase 5 types ──────────────────────────────────────────────────────────
export type NotificationKind = "info" | "running" | "complete" | "error";

export interface Notification {
  id: string;
  kind: NotificationKind;
  title: string;
  body?: string;
  /** auto-dismiss after ms (0 = manual only) */
  ttl?: number;
}

/** WO-9 Phase 1: a follow-up turn's payload — the answer synthesized from a
 *  prior run's STORED evidence (no re-convened firm), plus whether the model
 *  flagged a genuine evidence gap. */
export interface FollowupTurnData {
  answer: string;
  citations: string[];
  needsNewData: boolean;
  missingAgent: string | null;
  sourceRunId: string;
}

export interface Turn {
  id: string;
  query: string;
  profile: Profile;
  model: ModelChoice;
  status: TurnStatus;
  trace: ProgressEvent[];
  result?: RunResult;
  error?: string;
  via?: string;
  startedAt: number;
  /** "run" (default/absent, full firm convening) or "followup" (answered from
   *  stored evidence, WO-9 Phase 1). Absent = "run" for backward compat with
   *  every existing Turn-producing code path. */
  kind?: "run" | "followup";
  /** present only when kind === "followup". */
  followup?: FollowupTurnData;
  /** WO-9 Phase 2: the report's Markdown text as it streams in via progress
   *  events (stage:"report", phase:"chunk") — accumulated, rendered while
   *  status==="running" and no `result` has landed yet. Superseded by the
   *  authoritative `result.synthesize.report` once the run completes. */
  streamingReport?: string;
}

export type InspectorTab = "monitor" | "investigate";
export type PanelTab = "trace" | "dossier";

/** WO-8 Phase 3: a pinned step (a Bucket-1 agent or Bucket-2 partner, on one
 *  turn) from the Info tab's pin affordance. NOTE: distinct from Phase 5's
 *  `pinned: string[]` (whole-conversation pins on `rohan/web-ui-chrome`, not
 *  yet merged when this landed) — this is a per-STEP pin, in-memory only
 *  (Phase 5 owns persistence). Reconcile the two when both land on main. */
export interface PinnedStep {
  turnId: string;
  /** the agentId (Bucket-1) or persona (Bucket-2) this pin refers to */
  key: string;
  label: string;
}

export type InspectorSelection =
  | { kind: "none" }
  | { kind: "agent"; agentId: string; turnId: string }
  | { kind: "fact"; index: number; turnId: string }
  | { kind: "verdict"; persona: string; turnId: string }
  | { kind: "step"; stage: string; turnId: string };

interface FirmState {
  // top bar
  profile: Profile;
  model: ModelChoice;
  setProfile: (p: Profile) => void;
  setModel: (m: ModelChoice) => void;

  // thread
  turns: Turn[];
  running: boolean;
  activeConversationId: string | null;

  // inspector (legacy — kept for backward compat with command-palette etc.)
  inspectorTab: InspectorTab;
  inspectorOpen: boolean;
  selection: InspectorSelection;
  /** which turn the Monitor shows; null = follow the latest turn */
  monitorTurnId: string | null;
  setInspectorTab: (t: InspectorTab) => void;
  setInspectorOpen: (open: boolean) => void;
  setMonitorTurn: (id: string | null) => void;
  select: (sel: InspectorSelection) => void;

  // new panel state (WO-7)
  railOpen: boolean;
  panelOpen: boolean;
  panelWide: boolean;
  panelTab: PanelTab;
  focusRowId: string | null;
  setRailOpen: (open: boolean) => void;
  setPanelOpen: (open: boolean) => void;
  setPanelWide: (wide: boolean) => void;
  setPanelTab: (t: PanelTab) => void;
  setFocusRowId: (id: string | null) => void;

  // command palette
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;

  // plan mode (review-before-run)
  planMode: boolean;
  setPlanMode: (on: boolean) => void;
  pendingPlan: PlanEnvelope | null;
  planLoading: boolean;
  planError: string | null;
  requestPlan: (query: string) => Promise<void>;
  togglePlanAgent: (id: string) => void;
  setAllPlanAgents: (selected: boolean) => void;
  cancelPlan: () => void;
  approvePlan: () => Promise<void>;

  // history
  conversations: Conversation[];
  persistenceAvailable: boolean;
  historyQuery: string;
  setHistoryQuery: (q: string) => void;
  refreshConversations: () => Promise<void>;
  newChat: () => void;
  openConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, title: string) => Promise<void>;
  starConversation: (id: string, starred: boolean) => Promise<void>;
  removeConversation: (id: string) => Promise<void>;
  /** Delete ALL conversations (batch — fires one DELETE per conversation). */
  clearAllConversations: () => Promise<void>;
  /** Export a conversation's latest run to Markdown (download). Fetches from server if not active. */
  exportConversation: (id: string) => Promise<void>;

  // ── Phase 5: pinned conversations ─────────────────────────────────────────
  // IDs of pinned conversations; persisted in localStorage (degrades honestly if
  // unavailable — SSR / private-browsing environments).
  pinned: string[];
  pinConversation: (id: string) => void;
  unpinConversation: (id: string) => void;

  // ── Phase 5: run notifications (toasts) ───────────────────────────────────
  notifications: Notification[];
  addNotification: (n: Omit<Notification, "id">) => void;
  dismissNotification: (id: string) => void;

  // run
  submit: (query: string, opts?: { approvedPlan?: string[] }) => Promise<void>;
  /** Abort the current in-flight run (safe to call when nothing is running). */
  abortRun: () => void;

  // ── WO-9 Phase 1: main-chat follow-up over a run's stored evidence ────────
  /** Answer `question` from the active conversation's last real run's stored
   *  evidence — no re-convened firm. Requires activeConversationId to be set
   *  (callers should route through `ask`, not call this directly, unless they
   *  have already verified a completed run exists). */
  askFollowup: (question: string) => Promise<void>;
  /** Single routing decision point (per WO-9 Phase 1): auto-detects whether a
   *  query should be answered as a follow-up over stored evidence (existing
   *  conversation with at least one completed full run) or convene the full
   *  firm via `submit`. All entry points (composer, follow-up chips) should
   *  call this instead of `submit` directly. */
  ask: (query: string) => Promise<void>;

  // WO-8 Phase 3: per-step pin (Info tab) — see PinnedStep doc comment above.
  pinnedSteps: PinnedStep[];
  togglePinStep: (step: PinnedStep) => void;
  isStepPinned: (turnId: string, key: string) => boolean;
}

let _seq = 0;
const uid = (p: string) => `${p}_${Date.now().toString(36)}_${(_seq++).toString(36)}`;

export const useFirm = create<FirmState>((set, get) => ({
  profile: "simulate",
  model: "haiku",
  setProfile: (profile) => set({ profile }),
  setModel: (model) => set({ model }),

  turns: [],
  running: false,
  activeConversationId: null,

  inspectorTab: "monitor",
  inspectorOpen: true,
  selection: { kind: "none" },
  monitorTurnId: null,
  setInspectorTab: (inspectorTab) => set({ inspectorTab }),
  setInspectorOpen: (inspectorOpen) => set({ inspectorOpen, panelOpen: inspectorOpen }),
  setMonitorTurn: (monitorTurnId) =>
    set({ monitorTurnId, inspectorTab: "monitor", inspectorOpen: true, panelOpen: true }),
  select: (selection) =>
    set({
      selection,
      inspectorOpen: true,
      panelOpen: true,
      // Legacy: kept for backward compat with command-palette / investigate.tsx
      inspectorTab: selection.kind === "none" ? get().inspectorTab : "investigate",
      // WO-8 Phase 3: "click a trace row → Info". agent/verdict/fact selections all
      // open the Info view (panelTab "dossier") for that step/fact — NOT the Trace
      // tab — per the locked design (no separate "Dossier" tab; the cited facts +
      // full detail live inside each step's Info). Only `kind:"none"` leaves the
      // current tab alone.
      panelTab: selection.kind === "none" ? get().panelTab : "dossier",
      focusRowId:
        selection.kind === "agent"
          ? selection.agentId
          : selection.kind === "verdict"
            ? selection.persona
            : null,
    }),

  // new panel state (WO-7)
  railOpen: true,
  panelOpen: true,
  panelWide: false,
  panelTab: "trace",
  focusRowId: null,
  setRailOpen: (railOpen) => set({ railOpen }),
  setPanelOpen: (panelOpen) => set({ panelOpen, inspectorOpen: panelOpen }),
  setPanelWide: (panelWide) => set({ panelWide }),
  setPanelTab: (panelTab) => set({ panelTab }),
  setFocusRowId: (focusRowId) => set({ focusRowId }),

  paletteOpen: false,
  setPaletteOpen: (paletteOpen) => set({ paletteOpen }),

  planMode: false,
  setPlanMode: (planMode) => set({ planMode }),
  pendingPlan: null,
  planLoading: false,
  planError: null,

  requestPlan: async (query) => {
    const q = query.trim();
    const { profile, model, running, planLoading } = get();
    if (!q || running || planLoading) return;
    set({ planLoading: true, planError: null, pendingPlan: null });
    const plan = await fetchPlan({ query: q, profile, model });
    if (!plan) {
      set({ planLoading: false, planError: "Could not compute a plan — run directly instead." });
      return;
    }
    set({ planLoading: false, pendingPlan: plan });
  },

  togglePlanAgent: (id) =>
    set((s) => {
      if (!s.pendingPlan) return {};
      return {
        pendingPlan: {
          ...s.pendingPlan,
          agents: s.pendingPlan.agents.map((a) =>
            a.id === id ? { ...a, selected: !a.selected } : a,
          ),
        },
      };
    }),

  setAllPlanAgents: (selected) =>
    set((s) => {
      if (!s.pendingPlan) return {};
      return {
        pendingPlan: {
          ...s.pendingPlan,
          agents: s.pendingPlan.agents.map((a) => ({ ...a, selected })),
        },
      };
    }),

  cancelPlan: () => set({ pendingPlan: null, planError: null }),

  approvePlan: async () => {
    const plan = get().pendingPlan;
    if (!plan) return;
    const approvedPlan = plan.agents.filter((a) => a.selected).map((a) => a.id);
    set({ pendingPlan: null, planError: null });
    await get().submit(plan.query, { approvedPlan });
  },

  conversations: [],
  persistenceAvailable: false,
  historyQuery: "",
  setHistoryQuery: (historyQuery) => set({ historyQuery }),

  refreshConversations: async () => {
    const { conversations, available } = await listConversations();
    set({ conversations, persistenceAvailable: available });
  },

  newChat: () => {
    if (get().running) return;
    set({
      turns: [],
      activeConversationId: null,
      selection: { kind: "none" },
      inspectorTab: "monitor",
      panelTab: "trace",
      monitorTurnId: null,
      pendingPlan: null,
      planError: null,
      historyQuery: "", // #16 — a fresh chat clears the history search filter
    });
  },

  openConversation: async (id) => {
    if (get().running) return;
    const detail = await getConversation(id);
    set({
      activeConversationId: id,
      pendingPlan: null,
      planError: null,
      selection: { kind: "none" },
      monitorTurnId: null,
    });
    if (!detail) {
      // backend returned nothing (404 / offline) — show an empty restored thread
      set({ turns: [], inspectorTab: "monitor", panelTab: "trace" });
      return;
    }
    // Map each persisted RUN → a fully-rendered, complete Turn. The result dict the
    // server re-attached carries the dossier (both planes), roundtable spread, synthesis
    // and flags; we synthesise a static trace so the Monitor/Investigate render too.
    //
    // WO-9 Phase 1: a run persisted with via="followup" carries a minimal
    // {_via:"followup", answer, citations, needs_new_data, missing_agent,
    // source_run_id, ...} dict — NOT a real run_live result. Restoring it through
    // traceFromResult/the full Turn shape would render nonsense/empty, so it gets
    // the lightweight followup Turn variant instead. Real runs restore exactly as
    // today (no behavior change there).
    const runs = detail.runs ?? [];
    const turns: Turn[] = runs.map((r, i) => {
      const raw = r.result ?? undefined;
      if (raw && (raw as { _via?: string })._via === "followup") {
        const f = raw as unknown as {
          answer?: string;
          citations?: string[];
          needs_new_data?: boolean;
          missing_agent?: string | null;
          source_run_id?: string;
        };
        return {
          id: `${id}_${r.id ?? i}`,
          query: r.query,
          profile: "demo" as Profile,
          model: "default" as ModelChoice,
          status: "complete" as TurnStatus,
          trace: [],
          kind: "followup" as const,
          followup: {
            answer: f.answer ?? "",
            citations: f.citations ?? [],
            needsNewData: !!f.needs_new_data,
            missingAgent: f.missing_agent ?? null,
            sourceRunId: f.source_run_id ?? "",
          },
          via: r.via,
          startedAt: 0,
        };
      }
      const result = raw as RunResult | undefined;
      return {
        id: `${id}_${r.id ?? i}`,
        query: r.query,
        profile: (result?._replay
          ? "replay"
          : result?._simulated
            ? "simulate"
            : result?._mock === false
              ? "live"
              : "demo") as Profile,
        model: ((result?._model as string) || "default") as ModelChoice,
        status: "complete" as TurnStatus,
        trace: traceFromResult(result),
        result,
        via: r.via,
        startedAt: 0,
      };
    });
    set({ turns, selection: { kind: "none" }, inspectorTab: "monitor", panelTab: "trace" });
  },

  renameConversation: async (id, title) => {
    set((s) => ({
      conversations: s.conversations.map((c) => (c.id === id ? { ...c, title } : c)),
    }));
    await patchConversation(id, { title });
  },

  starConversation: async (id, starred) => {
    set((s) => ({
      conversations: s.conversations.map((c) => (c.id === id ? { ...c, starred } : c)),
    }));
    await patchConversation(id, { starred });
  },

  removeConversation: async (id) => {
    set((s) => ({
      conversations: s.conversations.filter((c) => c.id !== id),
      activeConversationId: s.activeConversationId === id ? null : s.activeConversationId,
      turns: s.activeConversationId === id ? [] : s.turns,
    }));
    await deleteConversation(id);
  },

  clearAllConversations: async () => {
    const ids = get().conversations.map((c) => c.id);
    // Optimistic: clear immediately
    set({ conversations: [], activeConversationId: null, turns: [] });
    // Fire deletes in parallel (best-effort; backend failures are non-fatal)
    await Promise.allSettled(ids.map((id) => deleteConversation(id)));
  },

  exportConversation: async (id) => {
    // First try the in-store turns (fast path when conversation is active)
    const { activeConversationId, turns } = get();
    if (activeConversationId === id) {
      const result = turns.slice().reverse().find((t) => t.status === "complete" && !!t.result)?.result;
      if (result) { await exportSynthesis(result, { download: true }); return; }
    }
    // Fallback: fetch from server
    const detail = await getConversation(id);
    const runs = detail?.runs ?? [];
    const latestResult = runs.slice().reverse().find((r) => !!r.result)?.result;
    if (latestResult) { await exportSynthesis(latestResult, { download: true }); return; }
    // Nothing to export — silent no-op (no report exists yet for this conversation)
  },

  abortRun: () => {
    const ac = (get() as unknown as { _runAbort: AbortController | null })._runAbort;
    if (ac) ac.abort();
  },

  // ── Phase 5: pinned conversations ─────────────────────────────────────────
  pinned: (() => {
    try {
      const raw = typeof localStorage !== "undefined" ? localStorage.getItem("sapphire:pinned") : null;
      return raw ? (JSON.parse(raw) as string[]) : [];
    } catch {
      return [];
    }
  })(),
  pinConversation: (id) =>
    set((s) => {
      if (s.pinned.includes(id)) return {};
      const next = [id, ...s.pinned];
      try { localStorage.setItem("sapphire:pinned", JSON.stringify(next)); } catch { /* noop */ }
      return { pinned: next };
    }),
  unpinConversation: (id) =>
    set((s) => {
      const next = s.pinned.filter((p) => p !== id);
      try { localStorage.setItem("sapphire:pinned", JSON.stringify(next)); } catch { /* noop */ }
      return { pinned: next };
    }),

  // ── Phase 5: run notifications ─────────────────────────────────────────────
  notifications: [],
  addNotification: (n) => {
    const id = uid("notif");
    set((s) => ({ notifications: [...s.notifications, { ...n, id }] }));
    if (n.ttl && n.ttl > 0) {
      setTimeout(() => {
        set((s) => ({ notifications: s.notifications.filter((x) => x.id !== id) }));
      }, n.ttl);
    }
  },
  dismissNotification: (id) =>
    set((s) => ({ notifications: s.notifications.filter((n) => n.id !== id) })),

  // Tracks the AbortController for the in-flight run so we can cancel it on
  // new-query or unmount. Stored outside Zustand state (closure var) — it's an
  // imperative handle, not view state.
  _runAbort: null as AbortController | null,

  submit: async (query, opts) => {
    const q = query.trim();
    const { profile, running } = get();
    if (!q && profile !== "replay") return;

    // Abort any in-flight run before starting a new one (new-query cancel).
    const prev = (get() as unknown as { _runAbort: AbortController | null })._runAbort;
    if (prev) prev.abort();
    if (running) {
      // Mark the previous turn as aborted if it was still running.
      set((s) => ({
        turns: s.turns.map((t) =>
          t.status === "running" ? { ...t, status: "error", error: "aborted" } : t,
        ),
      }));
    }

    const approvedPlan = opts?.approvedPlan;
    const ac = new AbortController();
    // Store the AbortController so unmount/new-query can cancel.
    (get() as unknown as { _runAbort: AbortController | null })._runAbort = ac;

    const turn: Turn = {
      id: uid("turn"),
      query: q || "(captured replay run)",
      profile,
      model: get().model,
      status: "running",
      trace: [],
      startedAt: Date.now(),
    };
    set((s) => ({
      turns: [...s.turns, turn],
      running: true,
      selection: { kind: "none" },
      inspectorTab: "monitor",
      panelTab: "trace",
      inspectorOpen: true,
      panelOpen: true,
      monitorTurnId: null, // a new turn returns the Monitor to "follow latest"
    }));

    // Phase 5: fire "Running…" toast on convene (survives navigation away)
    get().addNotification({
      kind: "running",
      title: "Running…",
      body: (q || "replay").slice(0, 60),
      ttl: 0, // manual dismiss; replaced by "complete" toast on finish
    });
    void turn.id; // Phase 5: runId captured above; used via turn.id closure in patchTurn

    const patchTurn = (patch: Partial<Turn>) =>
      set((s) => ({
        turns: s.turns.map((t) => (t.id === turn.id ? { ...t, ...patch } : t)),
      }));

    // Single set() per event — appends the event and applies the RAM cap in one
    // state transition to avoid double renders.
    const pushTrace = (ev: ProgressEvent) =>
      set((s) => {
        const turns = s.turns.map((t) =>
          t.id === turn.id ? { ...t, trace: [...t.trace, ev] } : t,
        );
        // RAM cap: keep full trace for last 3 turns; trim older to "done" events only
        const n = turns.length;
        if (n <= 3) return { turns };
        const trimmed = turns.map((t, i) => {
          if (i >= n - 3) return t;
          const doneOnly = t.trace.filter((e) => e.phase === "done" || e.phase === "rebuttal_done");
          return doneOnly.length === t.trace.length ? t : { ...t, trace: doneOnly };
        });
        return { turns: trimmed };
      });

    // ensure a conversation exists for persistence (best-effort; degrades to null)
    let convId = get().activeConversationId;
    if (!convId) {
      const created = await createConversation({
        title: q ? q.slice(0, 80) : "Captured replay",
        preview: q,
      });
      if (created?.id) {
        convId = created.id;
        set({ activeConversationId: convId });
        await get().refreshConversations();
      }
    }

    let finalResult: RunResult | undefined;
    try {
      await runFirm(
        {
          query: q,
          profile,
          model: get().model,
          conversation_id: convId ?? undefined,
          approved_plan: approvedPlan,
        },
        {
          onOpen: (ev) => patchTurn({ via: ev.via }),
          // WO-9 Phase 2: "report" stage events are the progressive-report stream —
          // they don't belong in the Trace/Monitor panel (would bloat it with dozens of
          // tiny per-token rows unrelated to the agent trace). "chunk" accumulates into
          // streamingReport; "done" needs no state change (the authoritative `result`
          // event lands moments later). Every OTHER stage keeps flowing to pushTrace
          // exactly as before.
          onProgress: (ev) => {
            if (ev.stage === "report") {
              if (ev.phase === "chunk" && ev.text) {
                const cur = get().turns.find((t) => t.id === turn.id);
                patchTurn({ streamingReport: (cur?.streamingReport ?? "") + ev.text });
              }
              return;
            }
            pushTrace(ev);
          },
          onResult: (result) => {
            finalResult = result;
            patchTurn({ result, status: "complete" });
            // Phase 5: replace "Running…" with "Run complete" toast
            const title = (result.query || q || "Run").slice(0, 55);
            // dismiss any running notification for this turn
            set((s) => ({
              notifications: s.notifications.filter(
                (n) => !(n.kind === "running" && n.body?.startsWith((q || "replay").slice(0, 20))),
              ),
            }));
            get().addNotification({
              kind: "complete",
              title: "Run complete",
              body: title,
              ttl: 6000,
            });
          },
          onError: (message) => {
            // Swallow AbortError — the user/component deliberately cancelled.
            if (ac.signal.aborted) return;
            patchTurn({ error: message, status: "error" });
            // Phase 5: fire error toast
            set((s) => ({
              notifications: s.notifications.filter((n) => n.kind !== "running"),
            }));
            get().addNotification({
              kind: "error",
              title: "Run failed",
              body: message.slice(0, 80),
              ttl: 8000,
            });
          },
          onDone: () => {
            // if a result never arrived and no error was set, mark complete-ish
            if (ac.signal.aborted) return;
            const cur = get().turns.find((t) => t.id === turn.id);
            if (cur && cur.status === "running") {
              patchTurn({ status: cur.result ? "complete" : "error", error: cur.error });
            }
          },
          signal: ac.signal,
        },
      );
    } catch (e) {
      if (!ac.signal.aborted) {
        patchTurn({
          status: "error",
          error: e instanceof Error ? e.message : "the firm could not be convened",
        });
      }
    } finally {
      // Always release the abort controller.
      if ((get() as unknown as { _runAbort: AbortController | null })._runAbort === ac) {
        (get() as unknown as { _runAbort: AbortController | null })._runAbort = null;
      }
      ac.abort(); // idempotent: closes the SSE ReadableStream reader on 'done'
      set({ running: false });
      // best-effort persist the turn onto the conversation
      if (convId && finalResult) {
        patchConversation(convId, {
          preview: q,
          last_result: finalResult,
        } as Partial<Conversation>).then(() => get().refreshConversations());
      }
    }
  },

  // ── WO-9 Phase 1: main-chat follow-up over a run's stored evidence ────────
  askFollowup: async (question) => {
    const q = question.trim();
    const convId = get().activeConversationId;
    if (!q || !convId) return;

    const turn: Turn = {
      id: uid("turn"),
      query: q,
      profile: get().profile,
      model: get().model,
      status: "running",
      trace: [],
      kind: "followup",
      startedAt: Date.now(),
    };
    set((s) => ({ turns: [...s.turns, turn] }));

    const result = await apiAskFollowup(convId, q);

    if (!result) {
      set((s) => ({
        turns: s.turns.map((t) =>
          t.id === turn.id
            ? {
                ...t,
                status: "error" as TurnStatus,
                error: "Could not answer from this run's evidence — try again.",
              }
            : t,
        ),
      }));
      get().addNotification({
        kind: "error",
        title: "Follow-up failed",
        body: q.slice(0, 80),
        ttl: 8000,
      });
      return;
    }

    set((s) => ({
      turns: s.turns.map((t) =>
        t.id === turn.id
          ? {
              ...t,
              status: "complete" as TurnStatus,
              followup: {
                answer: result.answer,
                citations: result.citations ?? [],
                needsNewData: !!result.needs_new_data,
                missingAgent: result.missing_agent ?? null,
                sourceRunId: result.source_run_id,
              },
            }
          : t,
      ),
    }));
  },

  ask: async (query) => {
    const q = query.trim();
    if (!q && get().profile !== "replay") return;
    const { activeConversationId, turns } = get();
    const hasCompletedRun = turns.some((t) => t.status === "complete" && !!t.result);
    if (activeConversationId && hasCompletedRun) {
      await get().askFollowup(q);
    } else {
      await get().submit(q);
    }
  },

  // WO-8 Phase 3: per-step pin (Info tab). In-memory only — Phase 5 owns
  // cross-reload persistence for the rail's Pinned section (see PinnedStep doc).
  pinnedSteps: [],
  togglePinStep: (step) =>
    set((s) => {
      const exists = s.pinnedSteps.some(
        (p) => p.turnId === step.turnId && p.key === step.key,
      );
      return {
        pinnedSteps: exists
          ? s.pinnedSteps.filter((p) => !(p.turnId === step.turnId && p.key === step.key))
          : [step, ...s.pinnedSteps],
      };
    }),
  isStepPinned: (turnId, key) =>
    get().pinnedSteps.some((p) => p.turnId === turnId && p.key === key),
}));
