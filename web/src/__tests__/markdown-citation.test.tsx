import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import React from "react";

// Mock store
const mockSelect = vi.fn();
vi.mock("@/lib/store", () => ({
  useFirm: (sel: (s: unknown) => unknown) => {
    const store = { select: mockSelect };
    return sel(store);
  },
}));

beforeEach(() => {
  mockSelect.mockClear();
});

describe("MarkdownDoc citation pills", () => {
  it("renders [[EMET]] as a clickable pill", async () => {
    const { MarkdownDoc } = await import("@/components/run/markdown");
    render(
      <MarkdownDoc
        text="Nav1.8 drives neuropathic pain signalling. [[EMET]]"
        turnId="turn-test-1"
      />
    );

    const pill = screen.getByText("EMET");
    expect(pill).toBeInTheDocument();
    // Pill should have role=button (clickable)
    expect(pill).toHaveAttribute("role", "button");
  });

  it("clicking EMET pill calls select with emet-runner agent", async () => {
    mockSelect.mockClear();
    const { MarkdownDoc } = await import("@/components/run/markdown");
    render(
      <MarkdownDoc
        text="Published evidence supports this claim. [[EMET]]"
        turnId="turn-test-2"
      />
    );

    const pill = screen.getByText("EMET");
    fireEvent.click(pill);

    expect(mockSelect).toHaveBeenCalledWith({
      kind: "agent",
      agentId: "emet-runner",
      turnId: "turn-test-2",
    });
  });

  it("renders [[Unknown Source]] as non-clickable muted pill", async () => {
    const { MarkdownDoc } = await import("@/components/run/markdown");
    render(
      <MarkdownDoc
        text="Some claim. [[Unknown Source]]"
        turnId="turn-test-3"
      />
    );

    const pill = screen.getByText("Unknown Source");
    expect(pill).toBeInTheDocument();
    // No role=button for unknown labels
    expect(pill).not.toHaveAttribute("role", "button");
  });

  it("renders [[Internal moat]] pill that navigates to internal-science-lead", async () => {
    mockSelect.mockClear();
    const { MarkdownDoc } = await import("@/components/run/markdown");
    render(
      <MarkdownDoc
        text="Internal CNS_DFP data confirms target expression. [[Internal moat]]"
        turnId="turn-test-4"
      />
    );

    const pill = screen.getByText("Internal moat");
    fireEvent.click(pill);

    expect(mockSelect).toHaveBeenCalledWith({
      kind: "agent",
      agentId: "internal-science-lead",
      turnId: "turn-test-4",
    });
  });

  it("renders bold and citation in same paragraph", async () => {
    const { MarkdownDoc } = await import("@/components/run/markdown");
    render(
      <MarkdownDoc
        text="**Nav1.8** is a validated target in neuropathic pain. [[EMET]]"
        turnId="turn-test-5"
      />
    );

    const bold = screen.getByText("Nav1.8");
    expect(bold.tagName).toBe("STRONG");

    const pill = screen.getByText("EMET");
    expect(pill).toBeInTheDocument();
  });

  it("renders without turnId - pills are non-clickable", async () => {
    const { MarkdownDoc } = await import("@/components/run/markdown");
    render(
      <MarkdownDoc text="Some claim. [[EMET]]" />
    );

    const pill = screen.getByText("EMET");
    expect(pill).toBeInTheDocument();
    // Without turnId, pills should not be clickable
    expect(pill).not.toHaveAttribute("role", "button");
  });

  it("renders h2 headings in violet with correct size", async () => {
    const { MarkdownDoc } = await import("@/components/run/markdown");
    render(
      <MarkdownDoc text="## Target and mechanism" turnId="turn-test-6" />
    );

    const heading = screen.getByText("Target and mechanism");
    expect(heading).toBeInTheDocument();
    // Heading should have violet color
    expect(heading).toHaveStyle({ color: "var(--color-accent)" });
    expect(heading).toHaveStyle({ fontSize: "19px" });
  });

  it("prose paragraphs use 16px font and var(--color-fg)", async () => {
    const { MarkdownDoc } = await import("@/components/run/markdown");
    render(
      <MarkdownDoc text="This is a prose paragraph with body text." turnId="turn-test-7" />
    );

    const para = screen.getByText("This is a prose paragraph with body text.");
    expect(para).toHaveStyle({ fontSize: "16px" });
    expect(para).toHaveStyle({ color: "var(--color-fg)" });
  });
});
