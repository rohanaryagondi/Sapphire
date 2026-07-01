/**
 * plan-tool-editing.test.tsx
 *
 * Tests that:
 * 1. PlanReview renders tools from tools_available with correct checked state.
 * 2. Toggling a tool updates the store's toolsOverride.
 * 3. approvePlan wires toolsOverride into the submit call's tools_override.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

// ── mocks ──────────────────────────────────────────────────────────────────
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

// Capture console errors to detect React warnings.
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
  vi.resetAllMocks();
});

// ── helpers ────────────────────────────────────────────────────────────────

/** A minimal PlanEnvelope that includes tools_available + tools_selected. */
function makePlan(
  toolsSelected: string[],
  toolsAvailable = [
    { id: "gnomad-constraint", name: "gnomAD Gene Constraint", purpose: "Fetch gnomAD constraint metrics." },
    { id: "gtex-expression",   name: "GTEx Tissue Expression",  purpose: "Retrieve median TPM values." },
    { id: "aso-tox",           name: "ASO Acute-Tox Screener",  purpose: "Predict acute toxicity." },
  ],
  toolRationale: Record<string, string> = {
    "gnomad-constraint": "Gene symbol detected — constraint relevant.",
    "gtex-expression":   "Gene symbol detected — expression relevant.",
    "aso-tox":           "No ASO sequences — skipped.",
  },
) {
  return {
    query: "Is SCN2A a good target for epilepsy?",
    agents: [],
    plan_source: "llm" as const,
    tools_selected: toolsSelected,
    tools_available: toolsAvailable,
    tool_rationale: toolRationale,
  };
}

// ── 1: render test ─────────────────────────────────────────────────────────

describe("PlanReview — tool editing panel", () => {
  it("renders tools from tools_available with correct checked state", async () => {
    const { useFirm } = await import("@/lib/store");
    const { PlanReview } = await import("@/components/plan-review");

    // Seed the store with a plan that has tools.
    const plan = makePlan(["gnomad-constraint", "gtex-expression"]);
    useFirm.setState({
      pendingPlan: plan,
      planLoading: false,
      planError: null,
      toolsOverride: null,
    });

    render(<PlanReview />);

    // The "Scientific tools" toggle header must be present.
    const toolsHeader = screen.getByText(/scientific tools/i);
    expect(toolsHeader).toBeInTheDocument();

    // The header says "2/3 selected" (2 of 3 available are in tools_selected).
    expect(screen.getByText(/2\/3 selected/i)).toBeInTheDocument();

    // Click to expand the tools section.
    fireEvent.click(toolsHeader.closest("button")!);

    // After expanding, all three tool names must appear.
    expect(screen.getByText("gnomAD Gene Constraint")).toBeInTheDocument();
    expect(screen.getByText("GTEx Tissue Expression")).toBeInTheDocument();
    expect(screen.getByText("ASO Acute-Tox Screener")).toBeInTheDocument();

    // The two selected tools must have aria-pressed="true".
    const gnomadBtn = screen.getByRole("button", { name: /gnomAD Gene Constraint/i });
    const gtexBtn   = screen.getByRole("button", { name: /GTEx Tissue Expression/i });
    const asoBtn    = screen.getByRole("button", { name: /ASO Acute-Tox Screener/i });

    // aria-pressed reflects checked state via data-tool-id attribute buttons.
    expect(gnomadBtn).toHaveAttribute("aria-pressed", "true");
    expect(gtexBtn).toHaveAttribute("aria-pressed", "true");
    expect(asoBtn).toHaveAttribute("aria-pressed", "false");

    // Rationale text for selected tools is shown.
    expect(screen.getByText("Gene symbol detected — constraint relevant.")).toBeInTheDocument();

    // No React console errors.
    const reactErrors = consoleErrors.filter(
      (e) => e.includes("Warning:") || e.includes("Error:") || e.includes("hook"),
    );
    expect(reactErrors, `Console errors:\n${reactErrors.join("\n")}`).toHaveLength(0);
  });

  // ── 2: toggle test ───────────────────────────────────────────────────────

  it("toggling a tool updates toolsOverride in the store", async () => {
    const { useFirm } = await import("@/lib/store");
    const { PlanReview } = await import("@/components/plan-review");

    const plan = makePlan(["gnomad-constraint"]);
    useFirm.setState({
      pendingPlan: plan,
      planLoading: false,
      planError: null,
      toolsOverride: null,
    });

    render(<PlanReview />);

    // Expand the tools section.
    fireEvent.click(screen.getByText(/scientific tools/i).closest("button")!);

    // Toggle "GTEx Tissue Expression" (currently deselected — not in tools_selected).
    const gtexBtn = screen.getByRole("button", { name: /GTEx Tissue Expression/i });
    expect(gtexBtn).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(gtexBtn);

    // After toggling, the store's toolsOverride must contain both gnomad and gtex.
    const { toolsOverride } = useFirm.getState();
    expect(toolsOverride).not.toBeNull();
    expect(toolsOverride).toContain("gnomad-constraint");
    expect(toolsOverride).toContain("gtex-expression");

    // The "edited" badge must appear in the header (toolsOverride !== null).
    expect(screen.getByText("edited")).toBeInTheDocument();
  });

  it("deselecting a selected tool removes it from toolsOverride", async () => {
    const { useFirm } = await import("@/lib/store");
    const { PlanReview } = await import("@/components/plan-review");

    const plan = makePlan(["gnomad-constraint", "gtex-expression"]);
    useFirm.setState({
      pendingPlan: plan,
      planLoading: false,
      planError: null,
      toolsOverride: null,
    });

    render(<PlanReview />);
    fireEvent.click(screen.getByText(/scientific tools/i).closest("button")!);

    // Deselect "gnomAD Gene Constraint".
    const gnomadBtn = screen.getByRole("button", { name: /gnomAD Gene Constraint/i });
    expect(gnomadBtn).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(gnomadBtn);

    const { toolsOverride } = useFirm.getState();
    expect(toolsOverride).not.toContain("gnomad-constraint");
    expect(toolsOverride).toContain("gtex-expression");
  });

  // ── 3: run payload test ──────────────────────────────────────────────────

  it("approvePlan wires toolsOverride into the submit call's tools_override", async () => {
    const { useFirm } = await import("@/lib/store");
    const apiModule = await import("@/lib/api");

    // Mock runFirm to capture what the store sends.
    let capturedRequest: Parameters<typeof apiModule.runFirm>[0] | null = null;
    vi.spyOn(apiModule, "runFirm").mockImplementation(async (req) => {
      capturedRequest = req;
    });

    const plan = makePlan(["gnomad-constraint"]);
    useFirm.setState({
      pendingPlan: plan,
      planLoading: false,
      planError: null,
      toolsOverride: ["gnomad-constraint", "gtex-expression"], // user added gtex
      turns: [],
      running: false,
      activeConversationId: null,
    });

    await useFirm.getState().approvePlan();

    // The run request must include tools_override with the user's edited set.
    expect(capturedRequest).not.toBeNull();
    expect((capturedRequest as { tools_override?: string[] }).tools_override).toEqual(
      expect.arrayContaining(["gnomad-constraint", "gtex-expression"]),
    );
    expect(
      ((capturedRequest as { tools_override?: string[] }).tools_override ?? []).length,
    ).toBe(2);
  });

  it("approvePlan uses plan.tools_selected when toolsOverride is null (no user edits)", async () => {
    const { useFirm } = await import("@/lib/store");
    const apiModule = await import("@/lib/api");

    let capturedRequest: Parameters<typeof apiModule.runFirm>[0] | null = null;
    vi.spyOn(apiModule, "runFirm").mockImplementation(async (req) => {
      capturedRequest = req;
    });

    const plan = makePlan(["gnomad-constraint", "aso-tox"]);
    useFirm.setState({
      pendingPlan: plan,
      planLoading: false,
      planError: null,
      toolsOverride: null, // no user edits
      turns: [],
      running: false,
      activeConversationId: null,
    });

    await useFirm.getState().approvePlan();

    // When no user edits, falls back to plan.tools_selected.
    expect(capturedRequest).not.toBeNull();
    const override = (capturedRequest as { tools_override?: string[] }).tools_override;
    expect(override).toEqual(expect.arrayContaining(["gnomad-constraint", "aso-tox"]));
    expect((override ?? []).length).toBe(2);
  });
});
