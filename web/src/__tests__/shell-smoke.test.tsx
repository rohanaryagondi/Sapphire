import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import * as TooltipPrimitive from "@radix-ui/react-tooltip";

// Mock Next.js navigation
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// Mock next/font
vi.mock("geist/font/sans", () => ({
  GeistSans: { variable: "--font-geist-sans", className: "geist-sans" },
}));
vi.mock("geist/font/mono", () => ({
  GeistMono: { variable: "--font-geist-mono", className: "geist-mono" },
}));

// Capture console errors
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

// Minimal wrapper that supplies the TooltipProvider context TopBar needs.
function Providers({ children }: { children: React.ReactNode }) {
  return <TooltipPrimitive.Provider>{children}</TooltipPrimitive.Provider>;
}

describe("App shell smoke test", () => {
  it("renders without crashing and zero React console errors", async () => {
    const { TopBar } = await import("@/components/topbar");
    const { render: renderLib } = await import("@testing-library/react");

    // TopBar is a client component that uses the zustand store — it should render without errors
    const { container } = renderLib(
      <Providers>
        <TopBar />
      </Providers>
    );

    // Should render something
    expect(container.firstChild).not.toBeNull();

    // Zero React console errors (Rules-of-Hooks violations, etc. appear here)
    const reactErrors = consoleErrors.filter(e =>
      e.includes("Warning:") || e.includes("Error:") || e.includes("hook")
    );
    expect(reactErrors, `Console errors:\n${reactErrors.join("\n")}`).toHaveLength(0);
  });

  it("renders the Sapphire brand", async () => {
    const { TopBar } = await import("@/components/topbar");
    render(
      <Providers>
        <TopBar />
      </Providers>
    );
    expect(screen.getByText("Sapphire")).toBeInTheDocument();
  });

  it("renders the Composer", async () => {
    const { Composer } = await import("@/components/composer");
    render(<Composer />);
    // Composer renders an input/textarea
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });
});
