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
  getConversation,
  listConversations,
  patchConversation,
  runFirm,
} from "./api";
import type {
  Conversation,
  ModelChoice,
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
  setInspectorTab: (t: InspectorTab) => void;
  setInspectorOpen: (open: boolean) => void;
  select: (sel: InspectorSelection) => void;

  // command palette
  paletteOpen: boolean;
  setPaletteOpen: (open: boolean) => void;

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
  submit: (query: string) => Promise<void>;
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
  setInspectorTab: (inspectorTab) => set({ inspectorTab }),
  setInspectorOpen: (inspectorOpen) => set({ inspectorOpen }),
  select: (selection) =>
    set({
      selection,
      inspectorOpen: true,
      inspectorTab: selection.kind === "none" ? get().inspectorTab : "investigate",
    }),

  paletteOpen: false,
  setPaletteOpen: (paletteOpen) => set({ paletteOpen }),

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
    });
  },

  openConversation: async (id) => {
    const conv = await getConversation(id);
    set({ activeConversationId: id });
    if (!conv) return;
    const turns: Turn[] = (conv.turns ?? []).map((t, i) => ({
      id: `${id}_${i}`,
      query: t.query,
      profile: (t.profile as Profile) ?? "demo",
      model: (t.model as ModelChoice) ?? "default",
      status: "complete" as TurnStatus,
      trace: t.trace ?? [],
      result: t.result,
      startedAt: 0,
    }));
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

  submit: async (query) => {
    const q = query.trim();
    const { profile, running } = get();
    if (running || (!q && profile !== "replay")) return;

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
        { query: q, profile, model: get().model, conversation_id: convId ?? undefined },
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
