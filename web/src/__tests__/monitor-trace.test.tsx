import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

// Mock Next.js navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock next/font
vi.mock("geist/font/sans", () => ({
  GeistSans: { variable: "--font-geist-sans", className: "geist-sans" },
}));
vi.mock("geist/font/mono", () => ({
  GeistMono: { variable: "--font-geist-mono", className: "geist-mono" },
}));

// Mock the virtualizer -- it needs DOM measurements we can't provide in jsdom
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (opts: { count: number; estimateSize: () => number }) => {
    const count = opts.count;
    const size = opts.estimateSize();
    return {
      getVirtualItems: () =>
        Array.from({ length: count }, (_, i) => ({
          index: i,
          key: i,
          start: i * size,
          size,
          lane: 0,
          end: (i + 1) * size,
        })),
      getTotalSize: () => count * size,
    };
  },
}));

// Shared spies so we can assert on them across render calls
const spySetPanelTab = vi.fn();
const spySelect = vi.fn();

// Mock the zustand store -- share spy instances so tests can assert on them
vi.mock("@/lib/store", () => ({
  useFirm: (selector: (s: unknown) => unknown) => {
    const store = {
      focusRowId: null,
      setFocusRowId: vi.fn(),
      turns: [],
      setMonitorTurn: vi.fn(),
      setPanelTab: spySetPanelTab,
      select: spySelect,
    };
    return selector(store);
  },
}));

const originalError = console.error;
let consoleErrors: string[] = [];
beforeEach(() => {
  consoleErrors = [];
  spySetPanelTab.mockClear();
  spySelect.mockClear();
  console.error = (...args: unknown[]) => {
    consoleErrors.push(args.map(String).join(" "));
  };
});
afterEach(() => {
  console.error = originalError;
});

const doneTurn = {
  id: "turn-1",
  query: "TSC2 viability in tuberous sclerosis",
  profile: "demo" as const,
  model: "default" as const,
  status: "complete" as const,
  startedAt: Date.now(),
  trace: [
    {
      stage: "bucket1",
      phase: "done",
      agent_id: "emet-runner",
      status: "ok",
      n_facts: 12,
      provenance: "emet-live",
      summary: "TSC2 drives mTORC1 hyperactivation in tuberous sclerosis cells",
    },
  ],
};

const runningTurn = {
  id: "turn-2",
  query: "NAV1.8 inhibitor selectivity",
  profile: "demo" as const,
  model: "default" as const,
  status: "running" as const,
  startedAt: Date.now(),
  trace: [
    {
      stage: "bucket1",
      phase: "start",
      agent_id: "emet-runner",
      status: "ok",
    },
  ],
};

describe("Monitor trace panel", () => {
  it("renders bucket1 summary text when done event carries summary", async () => {
    const { Monitor } = await import("@/components/inspector/monitor");
    const scrollRef = { current: null } as React.RefObject<HTMLDivElement | null>;
    render(<Monitor turn={doneTurn as any} outerScrollRef={scrollRef} />);

    expect(
      screen.getByText("TSC2 drives mTORC1 hyperactivation in tuberous sclerosis cells")
    ).toBeInTheDocument();

    const b1Headers = screen.getAllByText(/Bucket 1/i);
    expect(b1Headers.length).toBeGreaterThan(0);

    const EMOJI_RANGES = /[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}]/u;
    expect(EMOJI_RANGES.test(document.body.innerHTML)).toBe(false);

    const reactErrors = consoleErrors.filter(
      (e) => e.includes("Warning:") || e.includes("Error:") || e.includes("hook")
    );
    expect(reactErrors, `Console errors:\n${reactErrors.join("\n")}`).toHaveLength(0);
  });

  it("shows working indicator when turn is running and bucket not complete", async () => {
    const { Monitor } = await import("@/components/inspector/monitor");
    const scrollRef = { current: null } as React.RefObject<HTMLDivElement | null>;
    render(<Monitor turn={runningTurn as any} outerScrollRef={scrollRef} />);

    expect(screen.getByText(/working/i)).toBeInTheDocument();

    const reactErrors = consoleErrors.filter(
      (e) => e.includes("Warning:") || e.includes("Error:") || e.includes("hook")
    );
    expect(reactErrors, `Console errors:\n${reactErrors.join("\n")}`).toHaveLength(0);
  });

  it("clicking a done agent row selects it (the store opens Info)", async () => {
    const { Monitor } = await import("@/components/inspector/monitor");
    const scrollRef = { current: null } as React.RefObject<HTMLDivElement | null>;
    render(<Monitor turn={doneTurn as any} outerScrollRef={scrollRef} />);

    // The agent row button -- find by the agent label text
    const agentBtn = screen.getByText(/emet/i).closest("button");
    expect(agentBtn).not.toBeNull();
    fireEvent.click(agentBtn!);

    // Row click selects the agent; the store's `select` reducer is what switches
    // the panel to Info ("dossier") -- so the monitor's contract is the select
    // call, not a direct setPanelTab (the tab switch is covered by store tests).
    expect(spySelect).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "agent", agentId: "emet-runner" })
    );
  });
});
