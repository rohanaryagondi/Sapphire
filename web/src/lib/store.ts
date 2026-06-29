"use client";
/* ============================================================================
   The client-side firm store (Zustand). Owns: top-bar selectors, the active
   conversation thread (turns), the live trace per running turn, the inspector
   selection, and conversation history. Network lives in lib/api.ts; this is
   orchestration + view state only.
   ============================================================================ */
import { create } from "zustand";
import {
  createConversation,
  deleteConversation,
  fetchPlan,
  getConversation,
  listConversations,
  patchConversation,
  runFirm,
} from "./api";
import { traceFromResult } from "./restore";
import type {
  Conversation,
  ModelChoice,
  PlanEnvelope,
  ProgressEvent,
  Profile,
  RunResult,
} from "./types";

export type TurnStatus = "running" | "complete" | "error";

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
}

export type InspectorTab = "monitor" | "investigate";

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

  // inspector
  inspectorTab: InspectorTab;
  inspectorOpen: boolean;
  selection: InspectorSelection;
  /** which turn the Monitor shows; null = follow the latest turn */
  monitorTurnId: string | null;
  setInspectorTab: (t: InspectorTab) => void;
  setInspectorOpen: (open: boolean) => void;
  setMonitorTurn: (id: string | null) => void;
  select: (sel: InspectorSelection) => void;

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

  // run
  submit: (query: string, opts?: { approvedPlan?: string[] }) => Promise<void>;
}

let _seq = 0;
const uid = (p: string) => `${p}_${Date.now().toString(36)}_${(_seq++).toString(36)}`;

export const useFirm = create<FirmState>((set, get) => ({
  profile: "demo",
  model: "default",
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
  setInspectorOpen: (inspectorOpen) => set({ inspectorOpen }),
  setMonitorTurn: (monitorTurnId) =>
    set({ monitorTurnId, inspectorTab: "monitor", inspectorOpen: true }),
  select: (selection) =>
    set({
      selection,
      inspectorOpen: true,
      inspectorTab: selection.kind === "none" ? get().inspectorTab : "investigate",
    }),

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
      set({ turns: [], inspectorTab: "monitor" });
      return;
    }
    // Map each persisted RUN → a fully-rendered, complete Turn. The result dict the
    // server re-attached carries the dossier (both planes), roundtable spread, synthesis
    // and flags; we synthesise a static trace so the Monitor/Investigate render too.
    const runs = detail.runs ?? [];
    const turns: Turn[] = runs.map((r, i) => {
      const result = (r.result ?? undefined) as RunResult | undefined;
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
    set({ turns, selection: { kind: "none" }, inspectorTab: "monitor" });
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

  submit: async (query, opts) => {
    const q = query.trim();
    const { profile, running } = get();
    if (running || (!q && profile !== "replay")) return;
    const approvedPlan = opts?.approvedPlan;

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
      inspectorOpen: true,
      monitorTurnId: null, // a new turn returns the Monitor to "follow latest"
    }));

    const patchTurn = (patch: Partial<Turn>) =>
      set((s) => ({
        turns: s.turns.map((t) => (t.id === turn.id ? { ...t, ...patch } : t)),
      }));
    const pushTrace = (ev: ProgressEvent) =>
      set((s) => ({
        turns: s.turns.map((t) =>
          t.id === turn.id ? { ...t, trace: [...t.trace, ev] } : t,
        ),
      }));

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
          onProgress: (ev) => pushTrace(ev),
          onResult: (result) => {
            finalResult = result;
            patchTurn({ result, status: "complete" });
          },
          onError: (message) => patchTurn({ error: message, status: "error" }),
          onDone: () => {
            // if a result never arrived and no error was set, mark complete-ish
            const cur = get().turns.find((t) => t.id === turn.id);
            if (cur && cur.status === "running") {
              patchTurn({ status: cur.result ? "complete" : "error", error: cur.error });
            }
          },
        },
      );
    } catch (e) {
      patchTurn({
        status: "error",
        error: e instanceof Error ? e.message : "the firm could not be convened",
      });
    } finally {
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
}));
