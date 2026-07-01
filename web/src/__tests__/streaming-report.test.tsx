import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { Turn } from "@/lib/store";
import type { RunResult } from "@/lib/types";

// Mock the store — chat-thread.tsx's TurnView only needs a handful of selectors.
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

const RESULT: RunResult = {
  query: "Is TSC2 a viable target in tuberous sclerosis?",
  plan: { deliverable: "", disease: "", modality: "", agents: [], panel: [] },
  discover: { dossier: [], flags: { VETO: [], DIVERGENCE: [], KNOWN_UNKNOWNS: [] }, status: "complete", agents: [] },
  consult: { round1: [] },
  synthesize: {
    recommendation: "Advance",
    confidence: "high",
    proposed_experiment: "",
    entities: {},
    report: "## Target & mechanism\n\nTSC2 loss activates mTORC1 signaling, the final authoritative report.",
  },
  engagement_id: "eng-1",
};

const BASE_TURN: Turn = {
  id: "turn-1",
  query: "Is TSC2 a viable target in tuberous sclerosis?",
  profile: "live",
  model: "default",
  status: "running",
  trace: [],
  startedAt: 0,
};

describe("Progressive report streaming (WO-9 Phase 2)", () => {
  it("renders the growing streamingReport text while running and no result has landed", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn: Turn = {
      ...BASE_TURN,
      streamingReport: "## Target & mechanism\n\nTSC2 loss activates mTORC1 signaling",
    };
    render(<TurnView turn={turn} />);

    expect(screen.getByText(/TSC2 loss activates mTORC1 signaling/)).toBeInTheDocument();
    expect(screen.getByText(/writing the report/i)).toBeInTheDocument();
  });

  it("shows the generic typing indicator (not the report renderer) before any report text has streamed", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    render(<TurnView turn={BASE_TURN} />);

    expect(screen.queryByText(/writing the report/i)).not.toBeInTheDocument();
  });

  it("renders the authoritative result.synthesize.report once the turn completes (regression guard)", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn: Turn = {
      ...BASE_TURN,
      status: "complete",
      result: RESULT,
      streamingReport: "## Target & mechanism\n\nTSC2 loss activates mTORC1 signaling", // stale partial text
    };
    render(<TurnView turn={turn} />);

    // The authoritative final report text is shown.
    expect(screen.getByText(/the final authoritative report/)).toBeInTheDocument();
    // The "writing…" indicator is gone once the run is complete.
    expect(screen.queryByText(/writing the report/i)).not.toBeInTheDocument();
  });
});
