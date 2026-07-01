/**
 * Phase 5 — daily-use chrome: Pin/Workspace · ⌘K palette · run notifications
 * Tests that cover:
 *  1) Palette opens/closes via store.paletteOpen
 *  2) Palette shows jump-to-step entries from turn trace
 *  3) Palette shows pin command when an active conversation exists
 *  4) Pin adds / unpin removes (store slice behaviour)
 *  5) Pin persists to localStorage
 *  6) HistoryRail Pinned section renders pins / empty state
 *  7) Toast renders on addNotification; dismisses on X; auto-dismisses via ttl
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, act, waitFor } from "@testing-library/react";
import React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";

// ── environment mocks ──────────────────────────────────────────────────────

// cmdk uses ResizeObserver internally
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

// Mock the API so network calls don't fire in tests and overwrite our state
vi.mock("@/lib/api", () => ({
  listConversations: vi.fn().mockResolvedValue({ conversations: [], available: false }),
  getConversation: vi.fn().mockResolvedValue(null),
  createConversation: vi.fn().mockResolvedValue({ id: "mock-conv" }),
  patchConversation: vi.fn().mockResolvedValue(undefined),
  deleteConversation: vi.fn().mockResolvedValue(undefined),
  runFirm: vi.fn().mockResolvedValue(undefined),
  fetchPlan: vi.fn().mockResolvedValue(null),
}));

// cmdk and radix-ui call scrollIntoView and window.getComputedStyle on elements
if (!Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = vi.fn();
}
if (!window.getComputedStyle) {
  window.getComputedStyle = vi.fn().mockReturnValue({ getPropertyValue: vi.fn().mockReturnValue("") });
}

// ── localStorage mock ──────────────────────────────────────────────────────
// Use a fresh in-memory store per test rather than spying on the real localStorage
// (the Zustand store reads localStorage on module initialisation, so spies set
// after import won't catch the very first read).
const localStorageData: Record<string, string> = {};
const lsSetSpy = vi.fn((key: string, value: string) => { localStorageData[key] = value; });
const lsGetSpy = vi.fn((key: string) => localStorageData[key] ?? null);
const lsRemoveSpy = vi.fn((key: string) => { delete localStorageData[key]; });

Object.defineProperty(globalThis, "localStorage", {
  value: { getItem: lsGetSpy, setItem: lsSetSpy, removeItem: lsRemoveSpy, clear: vi.fn() },
  writable: true,
});

function Providers({ children }: { children: React.ReactNode }) {
  return <TooltipPrimitive.Provider>{children}</TooltipPrimitive.Provider>;
}

// ── reset store state between tests ───────────────────────────────────────
beforeEach(async () => {
  // Clear localStorage data between tests
  for (const k of Object.keys(localStorageData)) delete localStorageData[k];
  lsSetSpy.mockClear();
  lsGetSpy.mockClear();

  const { useFirm } = await import("@/lib/store");
  act(() => {
    useFirm.setState({
      paletteOpen: false,
      pinned: [],
      notifications: [],
      turns: [],
      activeConversationId: null,
      conversations: [],
      persistenceAvailable: false,
    });
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

// ── 1. Command Palette ─────────────────────────────────────────────────────
describe("CommandPalette", () => {
  it("renders closed when paletteOpen is false", async () => {
    const { CommandPalette } = await import("@/components/command-palette");
    render(
      <Providers>
        <CommandPalette />
      </Providers>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("renders open when paletteOpen is true", async () => {
    const { useFirm } = await import("@/lib/store");
    const { CommandPalette } = await import("@/components/command-palette");

    act(() => { useFirm.setState({ paletteOpen: true }); });

    render(
      <Providers>
        <CommandPalette />
      </Providers>,
    );

    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
    expect(screen.getByPlaceholderText("Type a command or search…")).toBeInTheDocument();
  });

  it("closes when paletteOpen set to false", async () => {
    const { useFirm } = await import("@/lib/store");
    const { CommandPalette } = await import("@/components/command-palette");

    act(() => { useFirm.setState({ paletteOpen: true }); });

    const { rerender } = render(
      <Providers>
        <CommandPalette />
      </Providers>,
    );

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    act(() => { useFirm.setState({ paletteOpen: false }); });
    rerender(
      <Providers>
        <CommandPalette />
      </Providers>,
    );

    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("shows 'New chat' command when open", async () => {
    const { useFirm } = await import("@/lib/store");
    const { CommandPalette } = await import("@/components/command-palette");

    act(() => { useFirm.setState({ paletteOpen: true }); });

    render(
      <Providers>
        <CommandPalette />
      </Providers>,
    );

    await waitFor(() => expect(screen.getByText("New chat")).toBeInTheDocument());
  });

  it("shows jump-to-step entries when the latest turn has a trace", async () => {
    const { useFirm } = await import("@/lib/store");
    const { CommandPalette } = await import("@/components/command-palette");

    act(() => {
      useFirm.setState({
        paletteOpen: true,
        turns: [
          {
            id: "t1",
            query: "Nav1.8 question",
            profile: "demo",
            model: "haiku",
            status: "complete",
            startedAt: 0,
            trace: [
              { stage: "bucket1", phase: "done", agent_id: "internal-science-lead" },
              { stage: "bucket1", phase: "done", agent_id: "emet-analyst" },
            ],
          },
        ],
      });
    });

    render(
      <Providers>
        <CommandPalette />
      </Providers>,
    );

    await waitFor(() => {
      expect(screen.getByText("Jump to step")).toBeInTheDocument();
      expect(screen.getByText("internal-science-lead")).toBeInTheDocument();
      expect(screen.getByText("emet-analyst")).toBeInTheDocument();
    });
  });

  it("shows 'Pin this conversation' when active and unpinned", async () => {
    const { useFirm } = await import("@/lib/store");
    const { CommandPalette } = await import("@/components/command-palette");

    act(() => {
      useFirm.setState({
        paletteOpen: true,
        activeConversationId: "conv-123",
        pinned: [],
        conversations: [{ id: "conv-123", title: "Nav1.8 run", preview: "" }],
      });
    });

    render(
      <Providers>
        <CommandPalette />
      </Providers>,
    );

    await waitFor(() => {
      expect(screen.getByText("Pin this conversation")).toBeInTheDocument();
    });
  });

  it("has zero React console errors when open", async () => {
    const { useFirm } = await import("@/lib/store");
    const { CommandPalette } = await import("@/components/command-palette");

    const errors: string[] = [];
    const orig = console.error;
    console.error = (...a: unknown[]) => errors.push(a.map(String).join(" "));

    act(() => { useFirm.setState({ paletteOpen: true }); });
    render(
      <Providers>
        <CommandPalette />
      </Providers>,
    );

    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());

    const reactErrors = errors.filter(
      (e) => e.includes("Warning:") || e.includes("Error:") || e.includes("hook"),
    );
    console.error = orig;
    expect(reactErrors).toHaveLength(0);
  });
});

// ── 2. Pin / Workspace ─────────────────────────────────────────────────────
describe("Pinned conversations", () => {
  it("pinConversation adds id to store.pinned", async () => {
    const { useFirm } = await import("@/lib/store");

    act(() => {
      useFirm.getState().pinConversation("conv-abc");
    });

    expect(useFirm.getState().pinned).toContain("conv-abc");
  });

  it("unpinConversation removes id from store.pinned", async () => {
    const { useFirm } = await import("@/lib/store");

    act(() => {
      useFirm.setState({ pinned: ["conv-abc", "conv-def"] });
      useFirm.getState().unpinConversation("conv-abc");
    });

    expect(useFirm.getState().pinned).not.toContain("conv-abc");
    expect(useFirm.getState().pinned).toContain("conv-def");
  });

  it("pinConversation persists to localStorage", async () => {
    const { useFirm } = await import("@/lib/store");

    act(() => {
      useFirm.setState({ pinned: [] });
      useFirm.getState().pinConversation("conv-persist");
    });

    expect(lsSetSpy).toHaveBeenCalledWith(
      "sapphire:pinned",
      expect.stringContaining("conv-persist"),
    );
  });

  it("does not add duplicate pins", async () => {
    const { useFirm } = await import("@/lib/store");

    act(() => {
      useFirm.setState({ pinned: ["conv-abc"] });
      useFirm.getState().pinConversation("conv-abc");
    });

    expect(useFirm.getState().pinned.filter((id) => id === "conv-abc")).toHaveLength(1);
  });

  it("HistoryRail renders Pinned section with pinned items", async () => {
    const { useFirm } = await import("@/lib/store");
    const { HistoryRail } = await import("@/components/history-rail");
    // Override the API mock for this test so refreshConversations returns the pinned conv
    const api = await import("@/lib/api");
    (api.listConversations as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      conversations: [{ id: "conv-pinned", title: "My Pinned Run", preview: "" }],
      available: true,
    });

    // Set state BEFORE rendering — pinned must survive the useEffect refresh
    act(() => {
      useFirm.setState({
        pinned: ["conv-pinned"],
        conversations: [{ id: "conv-pinned", title: "My Pinned Run", preview: "" }],
        persistenceAvailable: true,
      });
    });

    render(
      <Providers>
        <HistoryRail />
      </Providers>,
    );

    await waitFor(() => {
      expect(screen.getByText("Pinned")).toBeInTheDocument();
      // The pinned item appears in the Pinned rail section (may also appear in the conversation list)
      const items = screen.getAllByText("My Pinned Run");
      expect(items.length).toBeGreaterThanOrEqual(1);
    });
  });

  it("HistoryRail shows 'Nothing pinned yet' when empty", async () => {
    const { useFirm } = await import("@/lib/store");
    const { HistoryRail } = await import("@/components/history-rail");

    act(() => {
      useFirm.setState({ pinned: [], conversations: [] });
    });

    render(
      <Providers>
        <HistoryRail />
      </Providers>,
    );

    await waitFor(() => {
      expect(screen.getByText(/nothing pinned yet/i)).toBeInTheDocument();
    });
  });
});

// ── 3. Toast / run notifications ──────────────────────────────────────────
describe("ToastContainer", () => {
  it("does not render when there are no notifications", async () => {
    const { useFirm } = await import("@/lib/store");
    const { ToastContainer } = await import("@/components/toasts");

    act(() => { useFirm.setState({ notifications: [] }); });

    const { container } = render(
      <Providers>
        <ToastContainer />
      </Providers>,
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders a toast when addNotification is called", async () => {
    const { useFirm } = await import("@/lib/store");
    const { ToastContainer } = await import("@/components/toasts");

    render(
      <Providers>
        <ToastContainer />
      </Providers>,
    );

    act(() => {
      useFirm.getState().addNotification({
        kind: "running",
        title: "Running…",
        body: "Nav1.8 question",
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Running…")).toBeInTheDocument();
      expect(screen.getByText("Nav1.8 question")).toBeInTheDocument();
    });
  });

  it("renders a 'complete' toast with correct kind attribute", async () => {
    const { useFirm } = await import("@/lib/store");
    const { ToastContainer } = await import("@/components/toasts");

    render(
      <Providers>
        <ToastContainer />
      </Providers>,
    );

    act(() => {
      useFirm.getState().addNotification({
        kind: "complete",
        title: "Run complete",
        body: "Nav1.8 pain targets",
        ttl: 0,
      });
    });

    await waitFor(() => {
      const toast = screen.getByRole("status");
      expect(toast).toHaveAttribute("data-kind", "complete");
      expect(screen.getByText("Run complete")).toBeInTheDocument();
    });
  });

  it("dismisses a toast when the X button is clicked", async () => {
    const { useFirm } = await import("@/lib/store");
    const { ToastContainer } = await import("@/components/toasts");

    render(
      <Providers>
        <ToastContainer />
      </Providers>,
    );

    act(() => {
      useFirm.getState().addNotification({
        kind: "info",
        title: "Hello world",
        body: "Test body",
      });
    });

    await waitFor(() => expect(screen.getByText("Hello world")).toBeInTheDocument());

    const dismissBtn = screen.getByRole("button", { name: /dismiss notification/i });
    fireEvent.click(dismissBtn);

    await waitFor(() => expect(screen.queryByText("Hello world")).toBeNull());
  });

  it("auto-dismisses a toast after its ttl via store", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const { useFirm } = await import("@/lib/store");

    act(() => {
      useFirm.getState().addNotification({
        kind: "complete",
        title: "Auto dismiss",
        ttl: 100,
      });
    });

    // Notification should be present immediately
    expect(useFirm.getState().notifications.some((n) => n.title === "Auto dismiss")).toBe(true);

    // Advance timers so the setTimeout fires
    act(() => { vi.advanceTimersByTime(200); });

    // Should be gone from the store now
    expect(useFirm.getState().notifications.some((n) => n.title === "Auto dismiss")).toBe(false);

    vi.useRealTimers();
  });

  it("dismissNotification removes by id", async () => {
    const { useFirm } = await import("@/lib/store");

    act(() => {
      useFirm.setState({
        notifications: [
          { id: "n1", kind: "info", title: "First" },
          { id: "n2", kind: "info", title: "Second" },
        ],
      });
      useFirm.getState().dismissNotification("n1");
    });

    const { notifications } = useFirm.getState();
    expect(notifications.map((n) => n.id)).not.toContain("n1");
    expect(notifications.map((n) => n.id)).toContain("n2");
  });
});

// ── 4. HistoryRail duplicate-preview suppression ───────────────────────────
describe("HistoryRail duplicate-preview suppression", () => {
  it("does not render the preview when it is identical to the title", async () => {
    const { useFirm } = await import("@/lib/store");
    const { HistoryRail } = await import("@/components/history-rail");

    act(() => {
      useFirm.setState({
        conversations: [
          {
            id: "c1",
            title: "Is TSC2 a viable CNS target?",
            preview: "Is TSC2 a viable CNS target?",
          },
        ],
        pinned: [],
        persistenceAvailable: true,
        historyQuery: "",
      });
    });

    render(
      <Providers>
        <HistoryRail />
      </Providers>,
    );

    // The title appears once; the preview (same text) must NOT appear a second time.
    await waitFor(() => {
      const hits = screen.getAllByText("Is TSC2 a viable CNS target?");
      expect(hits).toHaveLength(1);
    });
  });

  it("renders the preview when it is distinct from the title", async () => {
    const { useFirm } = await import("@/lib/store");
    const { HistoryRail } = await import("@/components/history-rail");

    act(() => {
      useFirm.setState({
        conversations: [
          {
            id: "c2",
            title: "Nav1.8 pain targets",
            preview: "Full analysis of Nav1.8 as a pain target including safety profile",
          },
        ],
        pinned: [],
        persistenceAvailable: true,
        historyQuery: "",
      });
    });

    render(
      <Providers>
        <HistoryRail />
      </Providers>,
    );

    await waitFor(() => {
      expect(screen.getByText("Nav1.8 pain targets")).toBeInTheDocument();
      expect(
        screen.getByText(
          "Full analysis of Nav1.8 as a pain target including safety profile",
        ),
      ).toBeInTheDocument();
    });
  });

  it("suppresses preview when it is a truncated prefix of the title", async () => {
    const { useFirm } = await import("@/lib/store");
    const { HistoryRail } = await import("@/components/history-rail");

    act(() => {
      useFirm.setState({
        conversations: [
          {
            id: "c3",
            title: "Is TSC2 a viable CNS target for rapamycin?",
            preview: "Is TSC2 a viable CNS target",
          },
        ],
        pinned: [],
        persistenceAvailable: true,
        historyQuery: "",
      });
    });

    render(
      <Providers>
        <HistoryRail />
      </Providers>,
    );

    await waitFor(() => {
      // preview text must not appear independently
      expect(
        screen.queryByText("Is TSC2 a viable CNS target"),
      ).toBeNull();
    });
  });
});
