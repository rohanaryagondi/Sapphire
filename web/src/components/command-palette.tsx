"use client";
/* ============================================================================
   Phase 5 enhancement: jump-to-step (agents/partners in the current run) +
   Pin active conversation command.  Existing commands (new chat, profile,
   model, conversations) kept verbatim.  Zero emojis — lucide-react SVG only.
   ============================================================================ */
import * as React from "react";
import { Command } from "cmdk";
import {
  ArrowRight,
  Check,
  Cpu,
  FlaskConical,
  MessageSquarePlus,
  PanelRight,
  Pin,
  Play,
  SlidersHorizontal,
} from "lucide-react";
import { useFirm } from "@/lib/store";
import type { ModelChoice, Profile } from "@/lib/types";

// keep in sync with the empty-state suggestions (all 4)
const QUERIES = [
  "Which genes rescue the TSC2 phenotype the most?",
  "TSC2 in tuberous sclerosis — is it a tractable CNS target?",
  "Nav1.8 pain targets — what does the evidence say?",
  "Assess the regulatory + payer risk for an ASO in a rare CNS disease.",
];

const PROFILES: Profile[] = ["demo", "simulate", "live", "replay"];
const MODELS: ModelChoice[] = ["default", "sonnet", "haiku"];

export function CommandPalette() {
  const open = useFirm((s) => s.paletteOpen);
  const setOpen = useFirm((s) => s.setPaletteOpen);
  const newChat = useFirm((s) => s.newChat);
  const submit = useFirm((s) => s.submit);
  const setProfile = useFirm((s) => s.setProfile);
  const setModel = useFirm((s) => s.setModel);
  const profile = useFirm((s) => s.profile);
  const model = useFirm((s) => s.model);
  const setInspectorOpen = useFirm((s) => s.setInspectorOpen);
  const inspectorOpen = useFirm((s) => s.inspectorOpen);
  const conversations = useFirm((s) => s.conversations);
  const openConversation = useFirm((s) => s.openConversation);

  // Phase 5: jump-to-step — derive agent steps from the latest turn's trace
  const turns = useFirm((s) => s.turns);
  const select = useFirm((s) => s.select);
  const latestTurn = turns.length > 0 ? turns[turns.length - 1] : null;
  const steps = React.useMemo(() => {
    if (!latestTurn) return [];
    // Collect unique agent_ids from the trace
    const seen = new Set<string>();
    const result: { agentId: string; stage: string }[] = [];
    for (const ev of latestTurn.trace) {
      if (ev.agent_id && !seen.has(ev.agent_id)) {
        seen.add(ev.agent_id);
        result.push({ agentId: ev.agent_id, stage: ev.stage ?? "" });
      }
    }
    // Also include result-level agents if available
    const agents = latestTurn.result?.discover?.agents ?? [];
    for (const a of agents) {
      if (!seen.has(a.id)) {
        seen.add(a.id);
        result.push({ agentId: a.id, stage: "bucket1" });
      }
    }
    return result;
  }, [latestTurn]);

  // Phase 5: pin active conversation
  const activeConversationId = useFirm((s) => s.activeConversationId);
  const pinConversation = useFirm((s) => s.pinConversation);
  const pinned = useFirm((s) => s.pinned);
  const isActivePinned = activeConversationId ? pinned.includes(activeConversationId) : false;

  // global keyboard shortcuts
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(!useFirm.getState().paletteOpen);
      }
      // ⌘/ toggles inspector
      if ((e.metaKey || e.ctrlKey) && e.key === "/") {
        e.preventDefault();
        setInspectorOpen(!useFirm.getState().inspectorOpen);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen, setInspectorOpen]);

  const run = (fn: () => void) => {
    setOpen(false);
    // defer so the dialog closes cleanly first
    setTimeout(fn, 0);
  };

  return (
    <Command.Dialog
      open={open}
      onOpenChange={setOpen}
      label="Command palette"
      className="fixed left-1/2 top-[18vh] z-[100] w-[min(620px,92vw)] -translate-x-1/2 overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-panel-raised)] shadow-[0_24px_80px_rgba(0,0,0,0.65)]"
      overlayClassName="fixed inset-0 z-[99] bg-black/55 backdrop-blur-sm fadein"
    >
      <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-3">
        <SlidersHorizontal className="size-4 text-[var(--color-fg-subtle)]" />
        <Command.Input
          autoFocus
          placeholder="Type a command or search…"
          className="h-12 flex-1 bg-transparent text-[14px] text-[var(--color-fg)] outline-none placeholder:text-[var(--color-fg-faint)]"
        />
        <span className="kbd">esc</span>
      </div>
      <Command.List className="max-h-[52vh] overflow-y-auto p-2">
        <Command.Empty className="px-2 py-6 text-center text-[12.5px] text-[var(--color-fg-subtle)]">
          No results.
        </Command.Empty>

        <Group heading="Actions">
          <Item icon={<MessageSquarePlus className="size-3.5" />} onSelect={() => run(newChat)}>
            New chat
          </Item>
          <Item
            icon={<PanelRight className="size-3.5" />}
            onSelect={() => run(() => setInspectorOpen(!inspectorOpen))}
          >
            {inspectorOpen ? "Hide" : "Show"} inspector
            <Shortcut keys="⌘/" />
          </Item>
          {/* Phase 5: pin active conversation */}
          {activeConversationId && !isActivePinned && (
            <Item
              icon={<Pin className="size-3.5" />}
              onSelect={() => run(() => pinConversation(activeConversationId))}
            >
              Pin this conversation
            </Item>
          )}
        </Group>

        {/* Phase 5: jump-to-step (agents in the current run) */}
        {steps.length > 0 && (
          <Group heading="Jump to step">
            {steps.map(({ agentId }) => (
              <Item
                key={agentId}
                icon={<ArrowRight className="size-3.5" />}
                onSelect={() =>
                  run(() => {
                    if (!latestTurn) return;
                    select({ kind: "agent", agentId, turnId: latestTurn.id });
                  })
                }
              >
                {agentId}
              </Item>
            ))}
          </Group>
        )}

        <Group heading="Run a query">
          {QUERIES.map((q) => (
            <Item key={q} icon={<Play className="size-3.5" />} onSelect={() => run(() => submit(q))}>
              {q}
            </Item>
          ))}
        </Group>

        <Group heading="Profile">
          {PROFILES.map((p) => (
            <Item
              key={p}
              icon={<FlaskConical className="size-3.5" />}
              active={p === profile}
              onSelect={() => run(() => setProfile(p))}
            >
              Set profile · <span className="capitalize">{p}</span>
            </Item>
          ))}
        </Group>

        <Group heading="Model">
          {MODELS.map((m) => (
            <Item
              key={m}
              icon={<Cpu className="size-3.5" />}
              active={m === model}
              onSelect={() => run(() => setModel(m))}
            >
              Set model · <span className="capitalize">{m}</span>
            </Item>
          ))}
        </Group>

        {conversations.length > 0 && (
          <Group heading="Conversations">
            {conversations.slice(0, 8).map((c) => (
              <Item
                key={c.id}
                icon={<MessageSquarePlus className="size-3.5" />}
                onSelect={() => run(() => openConversation(c.id))}
              >
                {c.title || "Untitled"}
              </Item>
            ))}
          </Group>
        )}
      </Command.List>
    </Command.Dialog>
  );
}

function Group({ heading, children }: { heading: string; children: React.ReactNode }) {
  return (
    <Command.Group
      heading={heading}
      className="mb-1 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[10.5px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-[0.07em] [&_[cmdk-group-heading]]:text-[var(--color-fg-subtle)]"
    >
      {children}
    </Command.Group>
  );
}

function Item({
  icon,
  onSelect,
  children,
  active,
}: {
  icon: React.ReactNode;
  onSelect: () => void;
  children: React.ReactNode;
  active?: boolean;
}) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-[var(--radius-sm)] px-2 py-2 text-[13px] text-[var(--color-fg-muted)] outline-none transition-colors data-[selected=true]:bg-[var(--color-elevated)] data-[selected=true]:text-[var(--color-fg)]"
    >
      <span className="text-[var(--color-fg-subtle)]">{icon}</span>
      <span className="flex flex-1 items-center gap-1 truncate">{children}</span>
      {active && (
        <Check className="ml-auto size-3.5 shrink-0 text-[var(--color-accent)]" />
      )}
    </Command.Item>
  );
}

function Shortcut({ keys }: { keys: string }) {
  return <span className="kbd ml-auto">{keys}</span>;
}
