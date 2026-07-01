import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import type { Turn } from "@/lib/store";

// Mock the store — chat-thread.tsx's TurnView only needs a handful of selectors.
// `submit` is captured so we can assert the escalation button calls it with the
// right query, and never fires silently/automatically.
const submitMock = vi.fn();
const setPanelOpenMock = vi.fn();
const setPanelTabMock = vi.fn();
const selectMock = vi.fn();

vi.mock("@/lib/store", async () => {
  const actual = await vi.importActual<typeof import("@/lib/store")>("@/lib/store");
  return {
    ...actual,
    useFirm: (sel: (s: unknown) => unknown) => {
      const store = {
        setPanelOpen: setPanelOpenMock,
        setPanelTab: setPanelTabMock,
        select: selectMock,
        submit: submitMock,
      };
      return sel(store);
    },
  };
});

beforeEach(() => {
  submitMock.mockClear();
  setPanelOpenMock.mockClear();
  setPanelTabMock.mockClear();
  selectMock.mockClear();
});

const BASE_TURN: Turn = {
  id: "turn-1",
  query: "What is TSC2's mechanism?",
  profile: "demo",
  model: "default",
  status: "complete",
  trace: [],
  startedAt: 0,
  kind: "followup",
  followup: {
    answer: "TSC2 loss activates mTORC1 signaling. [[EMET]]",
    citations: ["EMET"],
    needsNewData: false,
    missingAgent: null,
    sourceRunId: "run-1",
  },
};

describe("Followup turn rendering (WO-9 Phase 1)", () => {
  it("renders the follow-up question and the answer with citation pills", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    render(<TurnView turn={BASE_TURN} />);

    expect(screen.getByText("What is TSC2's mechanism?")).toBeInTheDocument();
    expect(screen.getByText(/TSC2 loss activates mTORC1 signaling/)).toBeInTheDocument();
    // MarkdownDoc renders [[EMET]] as a citation pill — free citation rendering.
    expect(screen.getByText("EMET")).toBeInTheDocument();
  });

  it("does NOT show the escalation affordance when needsNewData is false", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    render(<TurnView turn={BASE_TURN} />);

    expect(screen.queryByText(/Run the full firm on this/i)).not.toBeInTheDocument();
  });

  it("shows the escalation affordance + names the missing agent when needsNewData is true", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn: Turn = {
      ...BASE_TURN,
      followup: {
        answer: "This run's evidence does not cover binding affinity for this compound.",
        citations: [],
        needsNewData: true,
        missingAgent: "a Q-Models binding-affinity run",
        sourceRunId: "run-1",
      },
    };
    render(<TurnView turn={turn} />);

    expect(screen.getByText(/a Q-Models binding-affinity run/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run the full firm on this/i })).toBeInTheDocument();
  });

  it("clicking the escalation button calls submit with the turn's query — not a silent auto re-run", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn: Turn = {
      ...BASE_TURN,
      query: "What is the binding affinity of compound X?",
      followup: {
        answer: "Not covered by this run.",
        citations: [],
        needsNewData: true,
        missingAgent: "a Q-Models binding-affinity run",
        sourceRunId: "run-1",
      },
    };
    render(<TurnView turn={turn} />);

    expect(submitMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Run the full firm on this/i }));
    expect(submitMock).toHaveBeenCalledTimes(1);
    expect(submitMock).toHaveBeenCalledWith("What is the binding affinity of compound X?");
  });

  it("renders an honest error banner when the followup turn errored", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn: Turn = {
      ...BASE_TURN,
      status: "error",
      error: "Could not answer from this run's evidence — try again.",
      followup: undefined,
    };
    render(<TurnView turn={turn} />);

    expect(screen.getByText(/Could not answer from this run's evidence/)).toBeInTheDocument();
    // Never fabricates: no answer content, no escalation button rendered from stale data.
    expect(screen.queryByRole("button", { name: /Run the full firm on this/i })).not.toBeInTheDocument();
  });

  it("does not render the full-firm chrome (trace pill / dossier) for a followup turn", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    render(<TurnView turn={BASE_TURN} />);
    expect(screen.queryByText(/Convened the firm/)).not.toBeInTheDocument();
  });
});
