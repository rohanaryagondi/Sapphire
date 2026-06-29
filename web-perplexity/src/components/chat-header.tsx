"use client";
import { Command, PanelRight } from "lucide-react";
import { Select, type SelectOption } from "@/components/ui/select";
import { Hint } from "@/components/ui/tooltip";
import { useFirm } from "@/lib/store";
import type { ModelChoice, Profile } from "@/lib/types";

const PROFILE_OPTS: SelectOption[] = [
  { value: "demo", label: "Demo", hint: "offline mock backends · $0 · deterministic", dot: "bg-[var(--color-fg-faint)]" },
  { value: "simulate", label: "Simulate", hint: "real moat/EMET/seams · 🧪 reasoning", dot: "bg-[var(--color-warn)]" },
  { value: "live", label: "Live", hint: "real backends · claude subagents", dot: "bg-[var(--color-ok)]" },
  { value: "replay", label: "Replay", hint: "frozen real capture · $0", dot: "bg-[var(--color-accent)]" },
];

const MODEL_OPTS: SelectOption[] = [
  { value: "default", label: "Default", hint: "engine-chosen model" },
  { value: "sonnet", label: "Sonnet", hint: "claude-sonnet — balanced" },
  { value: "haiku", label: "Haiku", hint: "claude-haiku — fast" },
];

export function ChatHeader() {
  const profile = useFirm((s) => s.profile);
  const model = useFirm((s) => s.model);
  const setProfile = useFirm((s) => s.setProfile);
  const setModel = useFirm((s) => s.setModel);
  const setPaletteOpen = useFirm((s) => s.setPaletteOpen);
  const inspectorOpen = useFirm((s) => s.inspectorOpen);
  const setInspectorOpen = useFirm((s) => s.setInspectorOpen);
  const running = useFirm((s) => s.running);

  const activeId = useFirm((s) => s.activeConversationId);
  const conversations = useFirm((s) => s.conversations);
  const title =
    conversations.find((c) => c.id === activeId)?.title ?? "New analysis";

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-[var(--color-border)] bg-[var(--color-panel)] px-4">
      <h1 className="min-w-0 flex-1 truncate text-[13px] font-semibold text-[var(--color-fg)]">
        {title}
      </h1>

      <button
        onClick={() => setPaletteOpen(true)}
        className="hidden items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2.5 py-1 text-[11.5px] text-[var(--color-fg-subtle)] transition-colors hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] md:flex"
      >
        <Command className="size-3" />
        Search
        <span className="kbd ml-0.5">⌘K</span>
      </button>

      {/* live model pill */}
      <div className="hidden items-center gap-1.5 rounded-full border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2.5 py-1 text-[11px] font-medium text-[var(--color-fg-subtle)] sm:flex">
        <span
          className={`h-1.5 w-1.5 rounded-full ${running ? "bg-[var(--color-accent)] live-dot" : "bg-[var(--color-ok)]"}`}
        />
        claude · sapphire-v3
      </div>

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

      <Hint label={inspectorOpen ? "Hide trace panel" : "Show trace panel"}>
        <button
          aria-pressed={inspectorOpen}
          onClick={() => setInspectorOpen(!inspectorOpen)}
          className={`flex size-8 items-center justify-center rounded-[var(--radius-sm)] border transition-colors ${
            inspectorOpen
              ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)] text-[var(--color-accent)]"
              : "border-[var(--color-border)] bg-[var(--color-panel)] text-[var(--color-fg-subtle)] hover:border-[var(--color-border-strong)]"
          }`}
        >
          <PanelRight className="size-3.5" />
        </button>
      </Hint>
    </header>
  );
}
