import "@testing-library/jest-dom";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Unmount every rendered tree after each test (RTL doesn't auto-register this
// for vitest without the `@testing-library/react/vitest` entry point). Without
// it, components from an earlier test stay mounted + subscribed to shared
// singletons (e.g. the zustand store), so a later test's state reset fires a
// React state update on an orphaned, un-acted instance ("not wrapped in
// act(...)" warnings) — that's what actually causes that noise, not the new
// test's own interactions.
afterEach(() => {
  cleanup();
});
