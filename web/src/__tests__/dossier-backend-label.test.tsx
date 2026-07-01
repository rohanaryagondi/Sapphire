import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";
import { backendLabel } from "@/lib/utils";
import type { RunResult } from "@/lib/types";

// ---------------------------------------------------------------------------
// backendLabel unit tests
// ---------------------------------------------------------------------------
describe("backendLabel", () => {
  it("returns simulated label for provenance 'simulated'", () => {
    expect(backendLabel("simulated")).toBe("Simulated -- no real model called");
  });

  it("returns qmodels label for provenance 'qmodels'", () => {
    expect(backendLabel("qmodels")).toBe("Q-Models launchpad");
  });

  it("returns Claude label with model for a reasoning agent", () => {
    expect(backendLabel("claude-reasoning", "haiku")).toBe("Claude · Haiku");
  });

  it("returns EMET label for provenance starting with 'emet'", () => {
    expect(backendLabel("emet-live")).toBe("EMET · BenchSci (live)");
  });

  it("returns Quiver data label for provenance starting with 'moat'", () => {
    expect(backendLabel("moat-real")).toBe("Quiver data (CNS_DFP)");
  });

  it("returns Curated dataset label for gnomad", () => {
    expect(backendLabel("gnomad")).toBe("Curated dataset");
  });

  it("returns Claude default when no runModel supplied for unknown provenance", () => {
    const result = backendLabel("some-unknown-prov");
    expect(result).toMatch(/^Claude · /);
    expect(result).toContain("default");
  });
});

// ---------------------------------------------------------------------------
// Dossier collapsible tests
// ---------------------------------------------------------------------------

// Mock the Zustand store
const mockSelect = vi.fn();
const mockState = {
  select: mockSelect,
  selection: { kind: "none" as const },
};
vi.mock("@/lib/store", () => ({
  useFirm: (sel: (s: typeof mockState) => unknown) => sel(mockState),
}));

function makeResult(dossierFacts: RunResult["discover"]["dossier"] = []): RunResult {
  return {
    query: "test",
    engagement_id: "eng_test",
    plan: { deliverable: "rec", disease: "pain", modality: "sm", agents: [], panel: [] },
    discover: {
      dossier: dossierFacts,
      flags: { VETO: [], DIVERGENCE: [], KNOWN_UNKNOWNS: [] },
      status: "complete",
      agents: [],
    },
    consult: { round1: [] },
    synthesize: {
      recommendation: "rec",
      confidence: "high",
      proposed_experiment: "",
      entities: {},
    },
    _elapsed_s: 1,
  };
}

describe("Dossier collapsible", () => {
  it("starts collapsed — body not in DOM", async () => {
    const { Dossier } = await import("@/components/run/dossier");
    const result = makeResult([
      { value: "Nav1.8 is expressed in DRG", source: "PMID:12345678", tier: "T1", provenance: "emet-live", plane: "external" },
    ]);
    render(<Dossier result={result} turnId="t1" />);
    // The dossier body should not be visible initially
    expect(screen.queryByTestId("dossier-body")).not.toBeInTheDocument();
    // The toggle button exists
    expect(screen.getByTestId("dossier-toggle")).toBeInTheDocument();
    // Fact text is not rendered yet
    expect(screen.queryByText("Nav1.8 is expressed in DRG")).not.toBeInTheDocument();
  });

  it("expands when toggle is clicked", async () => {
    const { Dossier } = await import("@/components/run/dossier");
    const result = makeResult([
      { value: "Nav1.8 is expressed in DRG", source: "PMID:12345678", tier: "T1", provenance: "emet-live", plane: "external" },
    ]);
    render(<Dossier result={result} turnId="t2" />);
    const toggle = screen.getByTestId("dossier-toggle");
    fireEvent.click(toggle);
    // After click, the dossier body is present
    expect(screen.getByTestId("dossier-body")).toBeInTheDocument();
  });

  it("shows fact count on the L1 toggle", async () => {
    const { Dossier } = await import("@/components/run/dossier");
    const result = makeResult([
      { value: "Fact A", source: "PMID:1111111", tier: "T1", provenance: "emet-live", plane: "external" },
      { value: "Fact B", source: "PMID:2222222", tier: "T2", provenance: "moat-real", plane: "internal" },
    ]);
    render(<Dossier result={result} turnId="t3" />);
    // Count badge shows total dossier length
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("returns null when dossier is empty", async () => {
    const { Dossier } = await import("@/components/run/dossier");
    const result = makeResult([]);
    const { container } = render(<Dossier result={result} turnId="t4" />);
    expect(container.firstChild).toBeNull();
  });
});
