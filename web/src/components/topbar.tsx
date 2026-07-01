"use client";
import { Command, Menu, PanelRight } from "lucide-react";
import { Select, type SelectOption } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Hint } from "@/components/ui/tooltip";
import { useFirm } from "@/lib/store";
import type { ModelChoice, Profile } from "@/lib/types";

const PROFILE_OPTS: SelectOption[] = [
  { value: "demo", label: "Demo", hint: "offline mock backends · $0 · deterministic", dot: "bg-[var(--color-fg-subtle)]" },
  { value: "simulate", label: "Simulate", hint: "real Quiver data/EMET/seams · sim reasoning", dot: "bg-[var(--color-warn)]" },
  { value: "live", label: "Live", hint: "real backends · claude subagents", dot: "bg-[var(--color-ok)]" },
  { value: "replay", label: "Replay", hint: "frozen real capture · $0", dot: "bg-[var(--color-external)]" },
];

const MODEL_OPTS: SelectOption[] = [
  { value: "default", label: "Default", hint: "engine-chosen model" },
  { value: "sonnet", label: "Sonnet", hint: "claude-sonnet — balanced" },
  { value: "haiku", label: "Haiku", hint: "claude-haiku — fast" },
];

export function TopBar() {
  const profile = useFirm((s) => s.profile);
  const model = useFirm((s) => s.model);
  const setProfile = useFirm((s) => s.setProfile);
  const setModel = useFirm((s) => s.setModel);
  const setPaletteOpen = useFirm((s) => s.setPaletteOpen);
  const railOpen = useFirm((s) => s.railOpen);
  const setRailOpen = useFirm((s) => s.setRailOpen);
  const panelOpen = useFirm((s) => s.panelOpen);
  const setPanelOpen = useFirm((s) => s.setPanelOpen);

  return (
    <header className="relative z-20 flex h-12 shrink-0 items-center justify-between border-b border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-bg)_82%,transparent)] px-3 backdrop-blur-xl">
      {/* left: hamburger + brand */}
      <div className="flex items-center gap-2">
        <Hint label={railOpen ? "Collapse history" : "Expand history"}>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setRailOpen(!railOpen)}
            aria-pressed={railOpen}
          >
            <Menu className="size-3.5" />
          </Button>
        </Hint>

        {/* brand */}
        <div className="flex items-center gap-2.5">
          <div className="relative flex h-6 w-6 items-center justify-center rounded-[7px] bg-gradient-to-br from-[#c4b5fd] to-[#8b5cf6] shadow-[0_0_0_1px_rgba(255,255,255,0.08),0_2px_8px_rgba(139,92,246,0.40)]">
            <svg viewBox="0 0 24 24" className="h-3.5 w-3.5 text-white" fill="none">
              <path
                d="M12 2 4 8l8 14 8-14-8-6Z"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
              <path d="M4 8h16M12 2v20" stroke="currentColor" strokeWidth="1" opacity="0.6" />
            </svg>
          </div>
          <div className="flex items-baseline gap-2">
            <span
              className="text-[14px] font-semibold tracking-tight"
              style={{ background: "linear-gradient(90deg, #f4f5f6, #cdbcff)", WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: "transparent" }}
            >
              Sapphire
            </span>
            <span className="hidden text-[11px] text-[var(--color-fg-subtle)] sm:inline">
              CNS decision firm
            </span>
          </div>
        </div>
      </div>

      {/* controls */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setPaletteOpen(true)}
          className="hidden items-center gap-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-elevated)] px-2 py-1.5 text-[12px] text-[var(--color-fg-subtle)] transition-colors hover:border-[var(--color-border-strong)] hover:text-[var(--color-fg-muted)] md:flex"
        >
          <Command className="size-3" />
          <span>Search</span>
          <span className="kbd ml-1">⌘K</span>
        </button>

        <Select
          label="model"
          value={model}
          options={MODEL_OPTS}
          onChange={(v) => setModel(v as ModelChoice)}
        />
        <Select
          label="profile"
          value={profile}
          options={PROFILE_OPTS}
          onChange={(v) => setProfile(v as Profile)}
        />

        <Hint label={panelOpen ? "Hide panel" : "Show panel"}>
          <Button
            variant="ghost"
            size="icon"
            aria-pressed={panelOpen}
            onClick={() => setPanelOpen(!panelOpen)}
            className={panelOpen ? "text-[var(--color-fg)]" : ""}
          >
            <PanelRight className="size-3.5" />
          </Button>
        </Hint>
      </div>
    </header>
  );
}
