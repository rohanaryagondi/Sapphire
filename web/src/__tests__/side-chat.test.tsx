import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import React from "react";
import type { Fact } from "@/lib/types";

// Mock the API seam — the component under test must forward the call exactly
// as given, never widening scope. Capture every call's arguments.
const askScopedMock = vi.fn(
  async (_q: string, _facts: Fact[], _agentId?: string, _detail?: Record<string, unknown> | null) => "mock answer",
);
vi.mock("@/lib/api", () => ({
  askScoped: (...args: [string, Fact[], string | undefined, Record<string, unknown> | null | undefined]) =>
    askScopedMock(...args),
}));

const originalError = console.error;
let consoleErrors: string[] = [];
beforeEach(() => {
  consoleErrors = [];
  askScopedMock.mockClear();
  console.error = (...args: unknown[]) => {
    consoleErrors.push(args.map(String).join(" "));
  };
});
afterEach(() => {
  console.error = originalError;
});

const STEP_FACTS: Fact[] = [
  { value: "TSC2 suppresses mTORC1", source: "PMID:12345", tier: "T2", provenance: "emet-live" },
];

// A larger "whole dossier" the component must NEVER see/send — proves the
// scoping guard: SideChat only ever forwards the `facts` prop it was given.
const WHOLE_DOSSIER: Fact[] = [
  ...STEP_FACTS,
  { value: "FZD7 WNT crosstalk", source: "PMID:99999", tier: "T2", provenance: "emet-live" },
  { value: "Internal moat score for DCTN6", source: "moat", tier: "T1", provenance: "moat-real" },
];

describe("SideChat", () => {
  it("renders without crashing and zero console errors", async () => {
    const { SideChat } = await import("@/components/inspector/side-chat");
    const { container } = render(<SideChat scopeLabel="emet-runner" facts={STEP_FACTS} agentId="emet-runner" />);
    expect(container.firstChild).not.toBeNull();
    const reactErrors = consoleErrors.filter((e) => e.includes("Warning:") || e.includes("hook"));
    expect(reactErrors, reactErrors.join("\n")).toHaveLength(0);
  });

  it("renders suggested questions and the input bar", async () => {
    const { SideChat } = await import("@/components/inspector/side-chat");
    render(<SideChat scopeLabel="emet-runner" facts={STEP_FACTS} agentId="emet-runner" />);
    expect(screen.getByText("What's the strongest fact here?")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/ask about/i)).toBeInTheDocument();
  });

  // ── the required scoping-guard test (DoD) ───────────────────────────────
  it("only ever sends the selected step's facts to askScoped — never the whole dossier", async () => {
    const { SideChat } = await import("@/components/inspector/side-chat");
    render(<SideChat scopeLabel="emet-runner" facts={STEP_FACTS} agentId="emet-runner" />);

    const input = screen.getByPlaceholderText(/ask about/i);
    fireEvent.change(input, { target: { value: "What does TSC2 do?" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(askScopedMock).toHaveBeenCalledTimes(1));
    const [question, sentFacts, agentId] = askScopedMock.mock.calls[0];
    expect(question).toBe("What does TSC2 do?");
    // The exact scoped list — identical to the prop, never the larger dossier.
    expect(sentFacts).toEqual(STEP_FACTS);
    expect(sentFacts).not.toEqual(WHOLE_DOSSIER);
    expect(sentFacts.length).toBe(1);
    expect(agentId).toBe("emet-runner");
  });

  // ── WO-9 Phase 3: detail forwarding (the follow-up chat should have access
  // to full per-agent evidence, not just the flattened fact list) ──────────
  it("forwards the agent's detail to askScoped when provided", async () => {
    const { SideChat } = await import("@/components/inspector/side-chat");
    const detail = { qmodels_tool_id: "dti", qmodels_tool_label: "DTI / Binder Triage" };
    render(<SideChat scopeLabel="q-models-runner" facts={STEP_FACTS} agentId="q-models-runner" detail={detail} />);

    const input = screen.getByPlaceholderText(/ask about/i);
    fireEvent.change(input, { target: { value: "Which tool ran?" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(askScopedMock).toHaveBeenCalledTimes(1));
    const [, , , sentDetail] = askScopedMock.mock.calls[0];
    expect(sentDetail).toEqual(detail);
  });

  it("omits detail (undefined) when the selected step has none — backward compatible", async () => {
    const { SideChat } = await import("@/components/inspector/side-chat");
    render(<SideChat scopeLabel="emet-runner" facts={STEP_FACTS} agentId="emet-runner" />);

    const input = screen.getByPlaceholderText(/ask about/i);
    fireEvent.change(input, { target: { value: "What does TSC2 do?" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => expect(askScopedMock).toHaveBeenCalledTimes(1));
    const [, , , sentDetail] = askScopedMock.mock.calls[0];
    expect(sentDetail).toBeUndefined();
  });

  it("clicking a suggested question sends it and shows the conversation view", async () => {
    const { SideChat } = await import("@/components/inspector/side-chat");
    render(<SideChat scopeLabel="emet-runner" facts={STEP_FACTS} agentId="emet-runner" />);

    fireEvent.click(screen.getByText("What's the strongest fact here?"));
    await waitFor(() => expect(askScopedMock).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByText("mock answer")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /detail/i })).toBeInTheDocument();
  });

  it("‹ detail returns from the conversation view to the suggestion view", async () => {
    const { SideChat } = await import("@/components/inspector/side-chat");
    render(<SideChat scopeLabel="emet-runner" facts={STEP_FACTS} agentId="emet-runner" />);

    fireEvent.click(screen.getByText("What's the strongest fact here?"));
    await waitFor(() => expect(screen.getByText("mock answer")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: /detail/i }));
    expect(screen.queryByText("mock answer")).not.toBeInTheDocument();
    expect(screen.getByText("What's the strongest fact here?")).toBeInTheDocument();
  });

  it("a prefill prop pre-fills the input (per-fact 'ask' affordance)", async () => {
    const { SideChat } = await import("@/components/inspector/side-chat");
    const onConsumed = vi.fn();
    render(
      <SideChat
        scopeLabel="emet-runner"
        facts={STEP_FACTS}
        agentId="emet-runner"
        prefill='About: "TSC2 suppresses mTORC1" — explain this.'
        onPrefillConsumed={onConsumed}
      />,
    );
    const input = screen.getByPlaceholderText(/ask about/i) as HTMLInputElement;
    await waitFor(() => expect(input.value).toContain("TSC2 suppresses mTORC1"));
    expect(onConsumed).toHaveBeenCalled();
  });
});
