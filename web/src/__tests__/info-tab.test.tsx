import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React, { act } from "react";
import type { RunResult } from "@/lib/types";
import type { Turn } from "@/lib/store";

vi.mock("@/lib/api", () => ({
  askScoped: vi.fn(async () => "mock answer"),
}));

const originalError = console.error;
let consoleErrors: string[] = [];
beforeEach(() => {
  consoleErrors = [];
  console.error = (...args: unknown[]) => {
    consoleErrors.push(args.map(String).join(" "));
  };
});
afterEach(async () => {
  console.error = originalError;
  const { useFirm } = await import("@/lib/store");
  act(() => {
    useFirm.setState({ turns: [], selection: { kind: "none" }, pinnedSteps: [] });
  });
});

const RESULT: RunResult = {
  query: "Is TSC2 a viable target in tuberous sclerosis?",
  plan: {
    deliverable: "diligence brief",
    disease: "tuberous sclerosis",
    modality: "small molecule",
    agents: ["emet-runner"],
    panel: ["Ex-FDA Regulator"],
  },
  discover: {
    dossier: [
      {
        value: "TSC2 suppresses mTORC1 signaling in neurons.",
        source: "PMID:12345",
        tier: "T2",
        provenance: "emet-live",
        plane: "external",
        agent_id: "emet-runner",
      },
    ],
    flags: { VETO: [], DIVERGENCE: [], KNOWN_UNKNOWNS: [] },
    status: "complete",
    agents: [{ id: "emet-runner", status: "ok", provenance: "emet-live", n_facts: 1, model: "EMET / BenchSci", agent_query: "SCN10A · neuropathic pain" }],
  },
  consult: {
    round1: [
      {
        persona: "Ex-FDA Regulator",
        stance: "caution",
        provenance: "persona-live",
        status: "ok",
        conviction: 3,
        rationale: "Needs a longer safety record before advancing.",
        fact_claims: ["PMID:12345"],
      },
    ],
    round2: [
      {
        persona: "Ex-FDA Regulator",
        // The engine's round-2 entries omit `stance` (it didn't change unless
        // `revised`) — see lib/verdicts.ts's doc comment. The TS contract still
        // marks it required, so the fixture carries the unchanged value too.
        stance: "caution",
        provenance: "persona-live",
        status: "ok",
        conviction: 3,
        revised: false,
        shift: "",
      },
    ],
  },
  synthesize: {
    recommendation: "Conditional advance",
    confidence: "Medium",
    proposed_experiment: "Mechanistic validation screen.",
    entities: {},
  },
  engagement_id: "eng_test1",
};

function makeTurn(): Turn {
  return {
    id: "turn_test1",
    query: "Is TSC2 a viable target in tuberous sclerosis?",
    profile: "live",
    model: "default",
    status: "complete",
    trace: [
      { stage: "bucket1", agent_id: "emet-runner", phase: "start" },
      {
        stage: "bucket1",
        agent_id: "emet-runner",
        phase: "done",
        status: "ok",
        provenance: "emet-live",
        n_facts: 1,
        elapsed_s: 1.2,
        summary: "TSC2 suppresses mTORC1 signaling per one cited PMID.",
      },
      {
        stage: "roundtable",
        agent_id: "Ex-FDA Regulator",
        phase: "rebuttal_done",
        status: "ok",
        stance: "caution",
        conviction: 3,
        provenance: "persona-live",
        round: 2,
        revised: false,
      },
    ],
    result: RESULT,
    startedAt: Date.now(),
  };
}

describe("InfoTab", () => {
  it("shows the empty state with no selection", async () => {
    const { InfoTab } = await import("@/components/inspector/info-tab");
    const turn = makeTurn();
    render(<InfoTab turn={turn} />);
    expect(screen.getByText(/click any agent or partner/i)).toBeInTheDocument();
  });

  it("renders a Bucket-1 agent step: takeaway, status/provenance, contributed facts", async () => {
    const { useFirm } = await import("@/lib/store");
    const { InfoTab } = await import("@/components/inspector/info-tab");
    const turn = makeTurn();
    act(() => {
      useFirm.setState({
        turns: [turn],
        selection: { kind: "agent", agentId: "emet-runner", turnId: turn.id },
      });
    });

    const { container } = render(<InfoTab turn={turn} />);

    // takeaway callout (the per-step summary)
    expect(screen.getByText(/TSC2 suppresses mTORC1 signaling per one cited PMID\./)).toBeInTheDocument();
    // the agent id + label
    expect(screen.getByText("emet-runner")).toBeInTheDocument();
    // the contributed fact, filtered by the new agent_id stamp
    expect(screen.getByText(/TSC2 suppresses mTORC1 signaling in neurons\./)).toBeInTheDocument();
    // side-chat mounted at the bottom
    expect(screen.getByPlaceholderText(/ask about/i)).toBeInTheDocument();

    const reactErrors = consoleErrors.filter((e) => e.includes("Warning:") || e.includes("hook"));
    expect(reactErrors, reactErrors.join("\n")).toHaveLength(0);
    expect(container.firstChild).not.toBeNull();
  });

  it("renders a Bucket-2 partner step: verdict, round evolution, rationale, cites", async () => {
    const { useFirm } = await import("@/lib/store");
    const { InfoTab } = await import("@/components/inspector/info-tab");
    const turn = makeTurn();
    act(() => {
      useFirm.setState({
        turns: [turn],
        selection: { kind: "verdict", persona: "Ex-FDA Regulator", turnId: turn.id },
      });
    });

    render(<InfoTab turn={turn} />);

    expect(screen.getByText("Ex-FDA Regulator")).toBeInTheDocument();
    expect(screen.getByText("caution")).toBeInTheDocument();
    // appears twice (the round-1 evolution line + the "full reasoning" block)
    expect(screen.getAllByText(/Needs a longer safety record/).length).toBeGreaterThanOrEqual(1);
    // round evolution shows both R1 and R2 markers
    expect(screen.getByText("R1")).toBeInTheDocument();
    expect(screen.getByText("R2")).toBeInTheDocument();
    // cited dossier fact (fact_claims)
    expect(screen.getByText("PMID:12345")).toBeInTheDocument();
  });

  it("shows model and agent_query KV rows for a Bucket-1 agent", async () => {
    const { useFirm } = await import("@/lib/store");
    const { InfoTab } = await import("@/components/inspector/info-tab");
    const turn = makeTurn();
    act(() => {
      useFirm.setState({
        turns: [turn],
        selection: { kind: "agent", agentId: "emet-runner", turnId: turn.id },
      });
    });

    render(<InfoTab turn={turn} />);

    // model KV row should show the recorded model
    expect(screen.getByText("EMET / BenchSci")).toBeInTheDocument();
    // agent_query KV row should show the scoped target
    expect(screen.getByText("SCN10A · neuropathic pain")).toBeInTheDocument();
  });

  // ── WO-9 Phase 3: full detail drill-down ────────────────────────────────
  it("renders agent.detail's extra keys when present (e.g. qmodels tool id/label)", async () => {
    const { useFirm } = await import("@/lib/store");
    const { InfoTab } = await import("@/components/inspector/info-tab");
    const turn = makeTurn();
    const withDetail: RunResult = {
      ...RESULT,
      discover: {
        ...RESULT.discover,
        agents: [
          {
            id: "emet-runner",
            status: "ok",
            provenance: "emet-live",
            n_facts: 1,
            model: "EMET / BenchSci",
            agent_query: "SCN10A · neuropathic pain",
            detail: {
              candidate: "SCN10A",
              facts: [],
              provenance: "emet-live",
              qmodels_tool_id: "dti",
              qmodels_tool_label: "DTI / Binder Triage",
            },
          },
        ],
      },
    };
    const detailTurn = { ...turn, result: withDetail };
    act(() => {
      useFirm.setState({
        turns: [detailTurn],
        selection: { kind: "agent", agentId: "emet-runner", turnId: turn.id },
      });
    });

    render(<InfoTab turn={detailTurn} />);

    expect(screen.getByText("Full detail")).toBeInTheDocument();
    expect(screen.getByText("qmodels_tool_id")).toBeInTheDocument();
    expect(screen.getByText("dti")).toBeInTheDocument();
    expect(screen.getByText("qmodels_tool_label")).toBeInTheDocument();
    expect(screen.getByText("DTI / Binder Triage")).toBeInTheDocument();
    // Keys already rendered elsewhere (facts/candidate/provenance) are skipped here.
    expect(screen.queryByText("candidate")).not.toBeInTheDocument();
  });

  it("renders nothing extra when agent.detail is absent/null (regression-safe)", async () => {
    const { useFirm } = await import("@/lib/store");
    const { InfoTab } = await import("@/components/inspector/info-tab");
    const turn = makeTurn();
    act(() => {
      useFirm.setState({
        turns: [turn],
        selection: { kind: "agent", agentId: "emet-runner", turnId: turn.id },
      });
    });

    render(<InfoTab turn={turn} />);

    expect(screen.queryByText("Full detail")).not.toBeInTheDocument();
  });

  it("the Pin button toggles pinnedSteps in the store", async () => {
    const { useFirm } = await import("@/lib/store");
    const { InfoTab } = await import("@/components/inspector/info-tab");
    const turn = makeTurn();
    act(() => {
      useFirm.setState({
        turns: [turn],
        selection: { kind: "agent", agentId: "emet-runner", turnId: turn.id },
      });
    });
    render(<InfoTab turn={turn} />);

    expect(useFirm.getState().isStepPinned(turn.id, "emet-runner")).toBe(false);
    fireEvent.click(screen.getByTitle(/pin to workspace/i));
    expect(useFirm.getState().isStepPinned(turn.id, "emet-runner")).toBe(true);
  });
});
