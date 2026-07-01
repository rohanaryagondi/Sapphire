/**
 * WO-9 Phase 7 — workspace polish tests.
 * Covers:
 *  1) Search filters conversation list by title (case-insensitive substring, live)
 *  2) Rename calls patchConversation API with the new title
 *  3) Delete calls deleteConversation API
 *  4) clearAllConversations fires deleteConversation for every conversation
 *  5) Default profile is "simulate" (not "demo" / "live")
 *  6) Export action calls getConversation + exportSynthesis on inactive conv
 */
import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";

// ── environment mocks ──────────────────────────────────────────────────────
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("geist/font/sans", () => ({
  GeistSans: { variable: "--font-geist-sans", className: "geist-sans" },
}));
vi.mock("geist/font/mono", () => ({
  GeistMono: { variable: "--font-geist-mono", className: "geist-mono" },
}));

// API mock — returned by name so individual tests can reconfigure
vi.mock("@/lib/api", () => ({
  listConversations: vi.fn().mockResolvedValue({ conversations: [], available: false }),
  getConversation: vi.fn().mockResolvedValue(null),
  createConversation: vi.fn().mockResolvedValue({ id: "mock-conv" }),
  patchConversation: vi.fn().mockResolvedValue(undefined),
  deleteConversation: vi.fn().mockResolvedValue(true),
  runFirm: vi.fn().mockResolvedValue(undefined),
  fetchPlan: vi.fn().mockResolvedValue(null),
  askFollowup: vi.fn().mockResolvedValue(null),
  askScoped: vi.fn().mockResolvedValue(""),
}));

// export-synthesis mock (we only test that it's called, not the Markdown output)
vi.mock("@/lib/export-synthesis", () => ({
  exportSynthesis: vi.fn().mockResolvedValue(undefined),
  buildSynthesisMarkdown: vi.fn().mockReturnValue("# mock"),
}));

if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn();
}
if (!window.getComputedStyle) {
  window.getComputedStyle = vi.fn().mockReturnValue({ getPropertyValue: vi.fn().mockReturnValue("") });
}

// localStorage mock
const localStorageData: Record<string, string> = {};
Object.defineProperty(globalThis, "localStorage", {
  value: {
    getItem: (k: string) => localStorageData[k] ?? null,
    setItem: (k: string, v: string) => { localStorageData[k] = v; },
    removeItem: (k: string) => { delete localStorageData[k]; },
    clear: vi.fn(),
  },
  writable: true,
});

function Providers({ children }: { children: React.ReactNode }) {
  return <TooltipPrimitive.Provider>{children}</TooltipPrimitive.Provider>;
}

beforeEach(async () => {
  for (const k of Object.keys(localStorageData)) delete localStorageData[k];
  const { useFirm } = await import("@/lib/store");
  act(() => {
    useFirm.setState({
      paletteOpen: false,
      pinned: [],
      notifications: [],
      turns: [],
      activeConversationId: null,
      conversations: [],
      persistenceAvailable: true,
      historyQuery: "",
      running: false,
    });
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

// ── 1. Search ───────────────────────────────────────────────────────────────
describe("HistoryRail search", () => {
  it("shows all conversations when query is empty", async () => {
    const { useFirm } = await import("@/lib/store");
    const { HistoryRail } = await import("@/components/history-rail");

    act(() => {
      useFirm.setState({
        conversations: [
          { id: "a", title: "Nav1.8 target" },
          { id: "b", title: "TSC2 question" },
        ],
      });
    });

    render(<Providers><HistoryRail /></Providers>);
    expect(screen.getByText("Nav1.8 target")).toBeDefined();
    expect(screen.getByText("TSC2 question")).toBeDefined();
  });

  it("filters conversations by title substring (case-insensitive)", async () => {
    const { useFirm } = await import("@/lib/store");
    const { HistoryRail } = await import("@/components/history-rail");

    act(() => {
      useFirm.setState({
        conversations: [
          { id: "a", title: "Nav1.8 target" },
          { id: "b", title: "TSC2 question" },
        ],
      });
    });

    render(<Providers><HistoryRail /></Providers>);
    const input = screen.getByPlaceholderText("Search conversations…");
    fireEvent.change(input, { target: { value: "tsc2" } });

    expect(screen.queryByText("Nav1.8 target")).toBeNull();
    expect(screen.getByText("TSC2 question")).toBeDefined();
  });

  it("shows 'No conversations match' when nothing matches the query", async () => {
    const { useFirm } = await import("@/lib/store");
    const { HistoryRail } = await import("@/components/history-rail");

    act(() => {
      useFirm.setState({
        conversations: [{ id: "a", title: "Nav1.8 target" }],
      });
    });

    render(<Providers><HistoryRail /></Providers>);
    const input = screen.getByPlaceholderText("Search conversations…");
    fireEvent.change(input, { target: { value: "zzznomatch" } });

    expect(screen.getByText("No conversations match.")).toBeDefined();
  });
});

// ── 2. Rename calls patchConversation ──────────────────────────────────────
describe("renameConversation store action", () => {
  it("calls patchConversation with the new title", async () => {
    const api = await import("@/lib/api");
    const { useFirm } = await import("@/lib/store");
    const patchSpy = api.patchConversation as Mock;

    act(() => {
      useFirm.setState({
        conversations: [{ id: "conv1", title: "Old title" }],
      });
    });

    await act(async () => {
      await useFirm.getState().renameConversation("conv1", "New title");
    });

    expect(patchSpy).toHaveBeenCalledWith("conv1", { title: "New title" });
    expect(useFirm.getState().conversations[0].title).toBe("New title");
  });
});

// ── 3. Delete calls deleteConversation ────────────────────────────────────
describe("removeConversation store action", () => {
  it("calls deleteConversation API", async () => {
    const api = await import("@/lib/api");
    const { useFirm } = await import("@/lib/store");
    const deleteSpy = api.deleteConversation as Mock;

    act(() => {
      useFirm.setState({
        conversations: [{ id: "conv1", title: "To delete" }],
        activeConversationId: null,
      });
    });

    await act(async () => {
      await useFirm.getState().removeConversation("conv1");
    });

    expect(deleteSpy).toHaveBeenCalledWith("conv1");
    expect(useFirm.getState().conversations).toHaveLength(0);
  });

  it("clears active conversation and turns when deleting the active one", async () => {
    const { useFirm } = await import("@/lib/store");
    act(() => {
      useFirm.setState({
        conversations: [{ id: "conv1", title: "Active" }],
        activeConversationId: "conv1",
        turns: [
          {
            id: "t1",
            query: "q",
            profile: "simulate",
            model: "haiku",
            status: "complete",
            trace: [],
            startedAt: 0,
          },
        ],
      });
    });

    await act(async () => {
      await useFirm.getState().removeConversation("conv1");
    });

    expect(useFirm.getState().activeConversationId).toBeNull();
    expect(useFirm.getState().turns).toHaveLength(0);
  });
});

// ── 4. Clear all conversations ────────────────────────────────────────────
describe("clearAllConversations store action", () => {
  it("fires deleteConversation for every conversation", async () => {
    const api = await import("@/lib/api");
    const { useFirm } = await import("@/lib/store");
    const deleteSpy = api.deleteConversation as Mock;

    act(() => {
      useFirm.setState({
        conversations: [
          { id: "a", title: "A" },
          { id: "b", title: "B" },
          { id: "c", title: "C" },
        ],
        activeConversationId: "a",
      });
    });

    await act(async () => {
      await useFirm.getState().clearAllConversations();
    });

    expect(deleteSpy).toHaveBeenCalledTimes(3);
    expect(deleteSpy).toHaveBeenCalledWith("a");
    expect(deleteSpy).toHaveBeenCalledWith("b");
    expect(deleteSpy).toHaveBeenCalledWith("c");
    expect(useFirm.getState().conversations).toHaveLength(0);
    expect(useFirm.getState().activeConversationId).toBeNull();
  });
});

// ── 5. Default profile ────────────────────────────────────────────────────
describe("store default profile", () => {
  it("defaults to 'simulate', not 'demo' or 'live'", async () => {
    // Re-import store fresh — the module initialises profile as a constant.
    // In test env, the Zustand store module is cached; we inspect the INITIAL value
    // from the store definition by checking what setState was called with at init time.
    // The simplest approach: after a full state reset (no override), check the default.
    const { useFirm } = await import("@/lib/store");
    // Read the initial-declaration default by resetting to an empty partial and
    // checking that profile wasn't overridden in beforeEach (we only reset specific keys).
    // The store's initialised value at module load time IS "simulate" per our edit.
    const initialProfile = useFirm.getInitialState?.().profile;
    // getInitialState may not exist on all Zustand versions; fall back to reading state
    // after a clean beforeEach (which doesn't override profile).
    const stateProfile = useFirm.getState().profile;
    // Either way it must be "simulate"
    const profile = initialProfile ?? stateProfile;
    expect(profile).toBe("simulate");
  });
});

// ── 6. Export conversation ────────────────────────────────────────────────
describe("exportConversation store action", () => {
  it("calls getConversation then exportSynthesis when conversation is not active", async () => {
    const api = await import("@/lib/api");
    const exportMod = await import("@/lib/export-synthesis");
    const { useFirm } = await import("@/lib/store");

    const mockResult = { query: "TSC2 test", engagement_id: "e1", synthesize: { report: "# Report" } };
    (api.getConversation as Mock).mockResolvedValueOnce({
      conversation: { id: "conv-x", title: "TSC2 test" },
      messages: [],
      runs: [{ id: "r1", query: "TSC2 test", result: mockResult }],
    });

    act(() => {
      useFirm.setState({ activeConversationId: "OTHER", conversations: [] });
    });

    await act(async () => {
      await useFirm.getState().exportConversation("conv-x");
    });

    expect(api.getConversation).toHaveBeenCalledWith("conv-x");
    expect(exportMod.exportSynthesis).toHaveBeenCalledWith(mockResult, { download: true });
  });

  it("uses active turn result directly without fetching when conversation is active", async () => {
    const api = await import("@/lib/api");
    const exportMod = await import("@/lib/export-synthesis");
    const { useFirm } = await import("@/lib/store");

    const mockResult = { query: "Nav1.8", engagement_id: "e2", synthesize: { report: "# Nav" } };
    act(() => {
      useFirm.setState({
        activeConversationId: "conv-active",
        turns: [
          {
            id: "t1",
            query: "Nav1.8",
            profile: "simulate",
            model: "haiku",
            status: "complete",
            trace: [],
            result: mockResult,
            startedAt: 0,
          },
        ],
      });
    });

    await act(async () => {
      await useFirm.getState().exportConversation("conv-active");
    });

    // Should NOT fetch from server when active turn has the result
    expect(api.getConversation).not.toHaveBeenCalled();
    expect(exportMod.exportSynthesis).toHaveBeenCalledWith(mockResult, { download: true });
  });
});
