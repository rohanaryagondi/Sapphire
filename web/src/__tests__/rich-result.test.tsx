import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import type { RunResult } from "@/lib/types";
import { buildSynthesisMarkdown } from "@/lib/export-synthesis";

// ---------------------------------------------------------------------------
// Mock the Zustand store
// ---------------------------------------------------------------------------
const mockSetPanelOpen = vi.fn();
const mockSetPanelTab = vi.fn();
const mockSelect = vi.fn();

const mockState = {
  panelOpen: false,
  setPanelOpen: mockSetPanelOpen,
  setPanelTab: mockSetPanelTab,
  select: mockSelect,
  selection: { kind: "none" as const },
  setMonitorTurn: vi.fn(),
};

vi.mock("@/lib/store", () => ({
  useFirm: (sel: (s: typeof mockState) => unknown) => sel(mockState),
}));

// ---------------------------------------------------------------------------
// Mock navigator.clipboard
// ---------------------------------------------------------------------------
beforeEach(() => {
  vi.stubGlobal("navigator", {
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
});

// ---------------------------------------------------------------------------
// Minimal RunResult factory
// ---------------------------------------------------------------------------
function makeResult(overrides: Partial<RunResult> = {}): RunResult {
  return {
    query: "Does Nav1.8 overexpression drive neuropathic pain?",
    engagement_id: "eng_test_001",
    plan: {
      deliverable: "recommendation",
      disease: "neuropathic pain",
      modality: "small molecule",
      agents: ["internal-science-lead", "emet-runner"],
      panel: ["Ex-FDA Regulator", "Adversarial Red-Team"],
    },
    discover: {
      dossier: [
        {
          value: "Nav1.8 is highly expressed in nociceptors",
          source: "PMID:12345678",
          tier: "T1",
          provenance: "emet-live",
          plane: "external",
        },
      ],
      flags: {
        VETO: [],
        DIVERGENCE: ["Nav1.8 expression diverges between internal and literature"],
        KNOWN_UNKNOWNS: ["Long-term safety profile not established"],
      },
      status: "complete",
      agents: [
        { id: "internal-science-lead", status: "ok", provenance: "moat-real", n_facts: 3 },
        { id: "emet-runner", status: "ok", provenance: "emet-live", n_facts: 5 },
      ],
    },
    consult: {
      round1: [
        {
          persona: "Ex-FDA Regulator",
          stance: "caution",
          provenance: "simulated",
          status: "ok",
          conviction: 6,
          rationale: "Needs more clinical evidence before regulatory submission.",
        },
        {
          persona: "Adversarial Red-Team",
          stance: "block",
          provenance: "simulated",
          status: "ok",
          conviction: 8,
          rationale: "Selectivity over Nav1.7 is unproven.",
        },
        {
          persona: "Payer",
          stance: "caution",
          provenance: "simulated",
          status: "ok",
          conviction: 5,
          rationale: "Reimbursement pathway unclear.",
        },
        {
          persona: "KOL",
          stance: "advance",
          provenance: "simulated",
          status: "ok",
          conviction: 7,
          rationale: "Strong mechanistic rationale supports advancement.",
        },
      ],
    },
    synthesize: {
      recommendation: "Advance Nav1.8 inhibitor program with selectivity screening.",
      confidence: "high",
      proposed_experiment: "Run Nav1.8 vs Nav1.7 patch-clamp selectivity assay.",
      entities: {
        ranked_candidates: [
          { rank: 1, gene: "SCN10A", reasoning: "Highest target score", source: "moat-real" },
          { rank: 2, gene: "SCN9A", reasoning: "Secondary target", source: "emet-live" },
        ],
        confidence_rationale: "Strong preclinical data supports this confidence level.",
        follow_up_questions: [
          "What is the IC50 of the lead compound on Nav1.8?",
          "Does Nav1.7 share the same binding pocket?",
        ],
      },
    },
    _elapsed_s: 42.3,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// 1. Synthesis renders recommendation
// ---------------------------------------------------------------------------
describe("Synthesis component", () => {
  it("renders the recommendation text", async () => {
    const { Synthesis } = await import("@/components/run/synthesis");
    const result = makeResult();
    render(<Synthesis result={result} />);
    expect(
      screen.getByText("Advance Nav1.8 inhibitor program with selectivity screening.")
    ).toBeInTheDocument();
  });

  // 2. Synthesis renders ranked candidates
  it("renders ranked candidates when present", async () => {
    const { Synthesis } = await import("@/components/run/synthesis");
    const result = makeResult();
    render(<Synthesis result={result} />);
    expect(screen.getByText("SCN10A")).toBeInTheDocument();
    expect(screen.getByText("SCN9A")).toBeInTheDocument();
  });

  it("does not render candidate section when absent", async () => {
    const { Synthesis } = await import("@/components/run/synthesis");
    const result = makeResult();
    (result.synthesize.entities as Record<string, unknown>).ranked_candidates = [];
    render(<Synthesis result={result} />);
    expect(screen.queryByText("Ranked candidates")).not.toBeInTheDocument();
  });

  // 3. Synthesis renders confidence with correct tone
  it("renders confidence value", async () => {
    const { Synthesis } = await import("@/components/run/synthesis");
    const result = makeResult();
    render(<Synthesis result={result} />);
    expect(screen.getByText("high")).toBeInTheDocument();
  });

  it("applies green tone class for high confidence", async () => {
    const { Synthesis } = await import("@/components/run/synthesis");
    const result = makeResult();
    render(<Synthesis result={result} />);
    const el = screen.getByText("high");
    expect(el.className).toContain("text-[var(--color-ok)]");
  });

  // 4. Synthesis shows Export button
  it("shows an Export button", async () => {
    const { Synthesis } = await import("@/components/run/synthesis");
    const result = makeResult();
    render(<Synthesis result={result} />);
    expect(screen.getByRole("button", { name: /export/i })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 5 + 6. Spread renders all verdicts unaveraged
// ---------------------------------------------------------------------------
describe("Spread component", () => {
  it("renders all 4 partner names without merging", async () => {
    const { Spread } = await import("@/components/run/spread");
    const result = makeResult();
    render(<Spread result={result} turnId="turn_1" />);
    expect(screen.getByText("Ex-FDA Regulator")).toBeInTheDocument();
    expect(screen.getByText("Adversarial Red-Team")).toBeInTheDocument();
    expect(screen.getByText("Payer")).toBeInTheDocument();
    expect(screen.getByText("KOL")).toBeInTheDocument();
    // The spread must never show a collapsed "Consensus" heading or "Average" verdict
    expect(screen.queryByText(/^Consensus$/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Average$/i)).not.toBeInTheDocument();
  });

  it("contains 'no forced consensus' label", async () => {
    const { Spread } = await import("@/components/run/spread");
    const result = makeResult();
    render(<Spread result={result} turnId="turn_1" />);
    expect(screen.getByText(/no forced consensus/i)).toBeInTheDocument();
  });

  it("renders conviction bars for each partner", async () => {
    const { Spread } = await import("@/components/run/spread");
    const result = makeResult();
    render(<Spread result={result} turnId="turn_1" />);
    // Each verdict card with conviction shows "X/10"
    const convictionLabels = screen.getAllByText(/\/10/);
    expect(convictionLabels.length).toBeGreaterThanOrEqual(4);
  });
});

// ---------------------------------------------------------------------------
// 7. Export buildSynthesisMarkdown
// ---------------------------------------------------------------------------
describe("buildSynthesisMarkdown", () => {
  it("contains the recommendation", () => {
    const result = makeResult();
    const md = buildSynthesisMarkdown(result);
    expect(md).toContain("Advance Nav1.8 inhibitor program with selectivity screening.");
  });

  it("contains partner persona names", () => {
    const result = makeResult();
    const md = buildSynthesisMarkdown(result);
    expect(md).toContain("Ex-FDA Regulator");
    expect(md).toContain("Adversarial Red-Team");
    expect(md).toContain("Payer");
    expect(md).toContain("KOL");
  });

  it("contains the footer sentinel", () => {
    const result = makeResult();
    const md = buildSynthesisMarkdown(result);
    expect(md).toContain("No facts fabricated");
  });

  it("does not contain the string 'undefined'", () => {
    const result = makeResult();
    const md = buildSynthesisMarkdown(result);
    expect(md).not.toContain("undefined");
  });

  it("does not contain the string 'null'", () => {
    const result = makeResult();
    const md = buildSynthesisMarkdown(result);
    expect(md).not.toContain("null");
  });

  it("omits missing sections gracefully", () => {
    const result = makeResult({
      synthesize: {
        recommendation: "A recommendation",
        confidence: "moderate",
        proposed_experiment: "",
        entities: {},
      },
    });
    const md = buildSynthesisMarkdown(result);
    expect(md).toContain("A recommendation");
    expect(md).not.toContain("Ranked Candidates");
    expect(md).not.toContain("Proposed Experiment");
    expect(md).not.toContain("undefined");
    expect(md).not.toContain("null");
  });

  it("marks round-2 rebuttal when present", () => {
    const result = makeResult();
    // Add round2 so isRebuttalRound returns true
    result.consult.round2 = result.consult.round1.map((v) => ({
      ...v,
      conviction: (v.conviction ?? 5) + 1,
      shift: "Position updated after rebuttal",
    }));
    const md = buildSynthesisMarkdown(result);
    expect(md).toContain("round 2 rebuttal");
  });
});

// ---------------------------------------------------------------------------
// 8. Inline trace pill on complete turn
// ---------------------------------------------------------------------------
describe("TurnView trace pill", () => {
  it("renders a 'show work' pill when turn is complete", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const result = makeResult();
    const turn = {
      id: "turn_pill_test",
      query: "Test query",
      profile: "live" as const,
      model: "haiku" as const,
      status: "complete" as const,
      trace: [],
      result,
      startedAt: Date.now(),
    };
    render(<TurnView turn={turn} />);
    expect(screen.getByText("show work")).toBeInTheDocument();
  });

  it("does not render trace pill when turn is still running", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn = {
      id: "turn_running_test",
      query: "Running query",
      profile: "live" as const,
      model: "haiku" as const,
      status: "running" as const,
      trace: [],
      startedAt: Date.now(),
    };
    render(<TurnView turn={turn} />);
    expect(screen.queryByText("show work")).not.toBeInTheDocument();
  });

  it("shows live trace links when turn is running", async () => {
    const { TurnView } = await import("@/components/chat-thread");
    const turn = {
      id: "turn_live_test",
      query: "Live query",
      profile: "live" as const,
      model: "haiku" as const,
      status: "running" as const,
      trace: [],
      startedAt: Date.now(),
    };
    render(<TurnView turn={turn} />);
    expect(screen.getByText("trace")).toBeInTheDocument();
  });
});
