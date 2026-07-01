import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import type { Turn } from "@/lib/store";

// Mock the store — mirrors followup-turn.test.tsx's harness exactly, adding
// reinvokeOnTurn (WO-9 Phase 5's targeted re-invocation action).
const submitMock = vi.fn();
const setPanelOpenMock = vi.fn();
const setPanelTabMock = vi.fn();
const selectMock = vi.fn();
const reinvokeOnTurnMock = vi.fn();

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
        reinvokeOnTurn: reinvokeOnTurnMock,
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
  reinvokeOnTurnMock.mockClear();
});

const BASE_TURN: Turn = {
  id: "turn-1",
  query: "Is TSC2 a viable target?",
  profile: "demo",
  model: "default",
  status: "complete",
  trace: [],
  startedAt: 0,
  kind: "followup",
  followup: {
    answer: "This run's evidence does not cover post-market safety for this class.",
    citations: [],
    needsNewData: true,
    missingAgent: "post-market-safety",
    missingAgentLabel: "Post-Market Safety",
    sourceRunId: "run-1",
  },
};

describe("Targeted re-invocation button (WO-9 Phase 5)", () => {
  it("renders the targeted 'Run <label>' button when missingAgent is a real id", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    render(<TurnView turn={BASE_TURN} />);

    expect(screen.getByRole("button", { name: /Run Post-Market Safety/i })).toBeInTheDocument();
    // Alongside, never replacing, the full-firm option.
    expect(screen.getByRole("button", { name: /Run the full firm on this/i })).toBeInTheDocument();
  });

  it("does NOT render the targeted button when missingAgent is null — only the full-firm option", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn: Turn = {
      ...BASE_TURN,
      followup: {
        answer: "No evidence gap the model could map to a real target.",
        citations: [],
        needsNewData: true,
        missingAgent: null,
        missingAgentLabel: null,
        sourceRunId: "run-1",
      },
    };
    render(<TurnView turn={turn} />);

    expect(screen.queryByRole("button", { name: /^Run Post-Market Safety$/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Run the full firm on this/i })).toBeInTheDocument();
  });

  it("clicking the targeted button calls reinvokeOnTurn with the turn id, agent id, and question", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    render(<TurnView turn={BASE_TURN} />);

    expect(reinvokeOnTurnMock).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Run Post-Market Safety/i }));
    expect(reinvokeOnTurnMock).toHaveBeenCalledTimes(1);
    expect(reinvokeOnTurnMock).toHaveBeenCalledWith("turn-1", "post-market-safety", "Is TSC2 a viable target?");
  });

  it("shows an in-flight indicator (pulsing dot) and disables the button while reinvoking", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn: Turn = {
      ...BASE_TURN,
      followup: { ...BASE_TURN.followup!, reinvoking: true },
    };
    render(<TurnView turn={turn} />);

    const btn = screen.getByRole("button", { name: /Running Post-Market Safety/i });
    expect(btn).toBeDisabled();
  });

  it("renders 'New evidence' distinctly above the answer once new_facts land", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn: Turn = {
      ...BASE_TURN,
      followup: {
        ...BASE_TURN.followup!,
        needsNewData: false,
        answer: "Updated answer incorporating the new FAERS signal.",
        newFacts: [
          { value: "FAERS shows elevated AE reports for this class.", source: "FAERS",
            tier: "T2", provenance: "semantic-web" },
        ],
      },
    };
    render(<TurnView turn={turn} />);

    expect(screen.getByText("New evidence")).toBeInTheDocument();
    expect(screen.getByText(/FAERS shows elevated AE reports/)).toBeInTheDocument();
    expect(screen.getByText(/Updated answer incorporating the new FAERS signal/)).toBeInTheDocument();
  });

  it("shows a reinvokeError message when the last re-invocation failed", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn: Turn = {
      ...BASE_TURN,
      followup: { ...BASE_TURN.followup!, reinvokeError: "post-market-safety abstained (status=escalated)" },
    };
    render(<TurnView turn={turn} />);

    expect(screen.getByText(/post-market-safety abstained/)).toBeInTheDocument();
  });
});
