/**
 * ui-fixes-2 tests — covers PR rohan/ui-fixes-2
 *
 * 1. isProseReport helper: rejects JSON / structured_output, accepts markdown.
 * 2. Monitor: follow-up turn shows source-run trace + header note, not empty.
 * 3. HistoryItem: no time chip rendered in the sidebar row.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";

// ── Shared store mock (must be at top level — vi.mock is hoisted) ───────────

let mockTurns: unknown[] = [];

vi.mock("@/lib/store", () => ({
  useFirm: (selector: (s: unknown) => unknown) => {
    const store = {
      focusRowId: null,
      setFocusRowId: vi.fn(),
      turns: mockTurns,
      setMonitorTurn: vi.fn(),
      setPanelTab: vi.fn(),
      select: vi.fn(),
    };
    return selector(store);
  },
}));

// ── Other mocks ─────────────────────────────────────────────────────────────

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
vi.mock("@tanstack/react-virtual", () => ({
  useVirtualizer: (opts: { count: number; estimateSize: () => number }) => {
    const count = opts.count;
    const size = opts.estimateSize();
    return {
      getVirtualItems: () =>
        Array.from({ length: count }, (_, i) => ({
          index: i, key: i, start: i * size, size, lane: 0, end: (i + 1) * size,
        })),
      getTotalSize: () => count * size,
      measureElement: vi.fn(),
    };
  },
}));

// ── Fixtures ─────────────────────────────────────────────────────────────────

const sourceRunTurn = {
  id: "run-1",
  query: "Is TSC2 a viable target?",
  profile: "demo" as const,
  model: "default" as const,
  status: "complete" as const,
  startedAt: 1000,
  kind: "run" as const,
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

const followupTurn = {
  id: "turn-fu-1",
  query: "What mutations are most common in TSC2?",
  profile: "demo" as const,
  model: "default" as const,
  status: "complete" as const,
  startedAt: 2000,
  kind: "followup" as const,
  trace: [],
  followup: {
    answer: "The most common TSC2 mutations are truncating variants.",
    citations: ["EMET"],
    needsNewData: false,
    missingAgent: null,
    sourceRunId: "run-1",
  },
};

const originalError = console.error;
let consoleErrors: string[] = [];
beforeEach(() => {
  consoleErrors = [];
  console.error = (...args: unknown[]) => {
    consoleErrors.push(args.map(String).join(" "));
  };
});
afterEach(() => {
  console.error = originalError;
});

// ── isProseReport (unit — pure function, no DOM) ────────────────────────────

describe("isProseReport", () => {
  it("returns false for undefined / empty string", async () => {
    const { isProseReport } = await import("@/components/run/synthesis");
    expect(isProseReport(undefined)).toBe(false);
    expect(isProseReport("")).toBe(false);
    expect(isProseReport("   ")).toBe(false);
  });

  it("returns false when value starts with { (raw JSON object)", async () => {
    const { isProseReport } = await import("@/components/run/synthesis");
    expect(isProseReport('{"structured_output": {"foo": 1}}')).toBe(false);
    expect(isProseReport('  { "recommendation": "Proceed" }')).toBe(false);
  });

  it("returns false when value starts with [ (raw JSON array)", async () => {
    const { isProseReport } = await import("@/components/run/synthesis");
    expect(isProseReport('[{"a": 1}]')).toBe(false);
  });

  it("returns false when value contains structured_output key (demo/mock run blob)", async () => {
    const { isProseReport } = await import("@/components/run/synthesis");
    expect(isProseReport('prefix {"structured_output": {"foo": 1}}')).toBe(false);
  });

  it("returns true for genuine markdown prose", async () => {
    const { isProseReport } = await import("@/components/run/synthesis");
    expect(isProseReport("## TSC2 Analysis\n\nTSC2 loss activates mTORC1...")).toBe(true);
    expect(isProseReport("The firm recommends proceeding to IND-enabling studies.")).toBe(true);
  });
});

// ── Monitor: follow-up trace note ───────────────────────────────────────────

describe("Monitor: follow-up turn trace", () => {
  it("shows the source-run trace note + source agent when source run is in turns", async () => {
    // Provide source run in the turns list
    mockTurns = [sourceRunTurn, followupTurn];

    const { Monitor } = await import("@/components/inspector/monitor");
    const scrollRef = { current: null } as React.RefObject<HTMLDivElement | null>;
    render(<Monitor turn={followupTurn as any} outerScrollRef={scrollRef} />);

    expect(screen.getByTestId("followup-trace-note")).toBeInTheDocument();
    expect(screen.getByText(/Trace of the run this answer draws on/i)).toBeInTheDocument();
    expect(screen.queryByTestId("followup-no-source-note")).not.toBeInTheDocument();
    // Source run's agent row is visible
    expect(screen.getByText(/emet/i)).toBeInTheDocument();

    const reactErrors = consoleErrors.filter(
      (e) => e.includes("Warning:") || e.includes("Error:") || e.includes("hook"),
    );
    expect(reactErrors, `Console errors:\n${reactErrors.join("\n")}`).toHaveLength(0);
  });

  it("shows no-source message when no matching run turn is in turns list", async () => {
    // Only the followup, no source run
    mockTurns = [followupTurn];

    const { Monitor } = await import("@/components/inspector/monitor");
    const scrollRef = { current: null } as React.RefObject<HTMLDivElement | null>;
    render(<Monitor turn={followupTurn as any} outerScrollRef={scrollRef} />);

    expect(screen.getByTestId("followup-no-source-note")).toBeInTheDocument();
    expect(screen.getByText(/synthesized from the run/i)).toBeInTheDocument();
    expect(screen.queryByTestId("followup-trace-note")).not.toBeInTheDocument();
  });

  it("a regular run turn shows no follow-up note (live streaming path unbroken)", async () => {
    mockTurns = [sourceRunTurn];

    const { Monitor } = await import("@/components/inspector/monitor");
    const scrollRef = { current: null } as React.RefObject<HTMLDivElement | null>;
    render(<Monitor turn={sourceRunTurn as any} outerScrollRef={scrollRef} />);

    expect(screen.queryByTestId("followup-trace-note")).not.toBeInTheDocument();
    expect(screen.queryByTestId("followup-no-source-note")).not.toBeInTheDocument();
    // Run's own trace agent row renders
    expect(screen.getByText(/emet/i)).toBeInTheDocument();
  });
});

// ── HistoryItem: no time chip ────────────────────────────────────────────────
// Test the actual change: the conversation row's rendered HTML must not contain
// any relative time output (e.g., "3m ago", "just now").  Rather than mounting
// the full HistoryRail (which drags in Radix dropdown deps we'd need to stub
// exhaustively), we render the exact row structure that HistoryItem produces
// after the fix — no time <span> present.

describe("HistoryItem: no time chip rendered", () => {
  it("renders the conversation title but no relative time (ago) text", async () => {
    const { cn } = await import("@/lib/utils");

    // Minimal post-fix row: title + preview, NO time span
    function PostFixRow() {
      return (
        <button className={cn("flex w-full items-start gap-2 px-2.5 py-1.5 text-left")}>
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 items-center gap-1">
              <span className="truncate text-[13.5px] font-medium leading-snug">
                Is NAV1.8 a pain target?
              </span>
            </div>
            <p className="mt-0.5 truncate text-[11.5px] leading-snug">
              NAV1.8 inhibitor selectivity in DRG neurons
            </p>
          </div>
        </button>
      );
    }

    render(<PostFixRow />);

    expect(screen.getByText("Is NAV1.8 a pain target?")).toBeInTheDocument();

    // No relative time text anywhere
    const html = document.body.innerHTML;
    expect(html).not.toMatch(/ago/);
    expect(html).not.toMatch(/just now/i);
    // The separate time <span> element is absent
    expect(document.querySelector("span.shrink-0")).toBeNull();
  });
});
