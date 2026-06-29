"use client";
import * as React from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Settings,
  Star,
  Trash2,
} from "lucide-react";
import { useFirm } from "@/lib/store";
import { cn, relTime } from "@/lib/utils";
import type { Conversation } from "@/lib/types";

/* the Sapphire gem mark — kept across both flagship designs */
function Gem({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none">
      <path
        d="M12 2 4 8l8 14 8-14-8-6Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M4 8h16M12 2v20" stroke="currentColor" strokeWidth="1" opacity="0.5" />
    </svg>
  );
}

export function HistoryRail() {
  const conversations = useFirm((s) => s.conversations);
  const available = useFirm((s) => s.persistenceAvailable);
  const activeId = useFirm((s) => s.activeConversationId);
  const running = useFirm((s) => s.running);
  const query = useFirm((s) => s.historyQuery);
  const setQuery = useFirm((s) => s.setHistoryQuery);
  const refresh = useFirm((s) => s.refreshConversations);
  const newChat = useFirm((s) => s.newChat);
  const open = useFirm((s) => s.openConversation);

  React.useEffect(() => {
    refresh();
  }, [refresh]);

  const filtered = React.useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = q
      ? conversations.filter(
          (c) =>
            (c.title ?? "").toLowerCase().includes(q) ||
            (c.preview ?? "").toLowerCase().includes(q),
        )
      : conversations;
    return [...list].sort((a, b) => Number(!!b.starred) - Number(!!a.starred));
  }, [conversations, query]);

  return (
    <div className="flex h-full flex-col">
      {/* brand */}
      <div className="flex h-12 shrink-0 items-center gap-2.5 border-b border-[var(--color-border)] px-3.5">
        <div className="flex size-6 items-center justify-center rounded-[7px] bg-gradient-to-br from-[#1a73e8] to-[#6d28d9] text-white shadow-sm">
          <Gem className="size-3.5" />
        </div>
        <div className="leading-none">
          <div className="text-[14px] font-bold tracking-tight text-[var(--color-fg)]">
            Sapphire
          </div>
          <div className="mt-0.5 text-[9.5px] font-medium uppercase tracking-[0.08em] text-[var(--color-fg-faint)]">
            CNS Discovery Firm
          </div>
        </div>
      </div>

      {/* new query */}
      <div className="px-2.5 pt-2.5">
        <button
          onClick={() => newChat()}
          disabled={running}
          className="flex w-full items-center gap-2 rounded-[var(--radius-sm)] border border-dashed border-[var(--color-border-strong)] bg-transparent px-2.5 py-2 text-[12.5px] font-medium text-[var(--color-fg-subtle)] transition-colors hover:border-[var(--color-accent)] hover:bg-[var(--color-accent-soft)] hover:text-[var(--color-accent)] disabled:opacity-50"
        >
          <Plus className="size-3.5" />
          New query
        </button>
      </div>

      {/* search */}
      <div className="px-2.5 py-2">
        <div className="flex items-center gap-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2 focus-within:border-[var(--color-accent)]">
          <Search className="size-3 text-[var(--color-fg-faint)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search analyses…"
            className="h-7 flex-1 bg-transparent text-[12.5px] text-[var(--color-fg)] outline-none placeholder:text-[var(--color-fg-faint)]"
          />
        </div>
      </div>

      {/* list */}
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        <div className="px-1.5 pb-1 pt-1 text-[10px] font-semibold uppercase tracking-[0.07em] text-[var(--color-fg-faint)]">
          History
        </div>
        {filtered.length === 0 ? (
          <p className="px-2 py-6 text-[12px] leading-relaxed text-[var(--color-fg-subtle)]">
            {available
              ? query
                ? "No analyses match."
                : "No analyses yet. Convene the firm to start one."
              : "History isn't connected yet. Your current session still works — start a new query."}
          </p>
        ) : (
          <div className="space-y-0.5">
            {filtered.map((c) => (
              <HistoryItem
                key={c.id}
                conv={c}
                active={c.id === activeId}
                onOpen={() => !running && open(c.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* profile footer */}
      <div className="shrink-0 border-t border-[var(--color-border)] p-2">
        <div className="flex items-center gap-2.5 rounded-[var(--radius-sm)] px-2 py-1.5 transition-colors hover:bg-[var(--color-bg-subtle)]">
          <div className="flex size-7 items-center justify-center rounded-full bg-gradient-to-br from-[#6d28d9] to-[#1a73e8] text-[10px] font-bold text-white">
            RA
          </div>
          <div className="min-w-0 flex-1 leading-tight">
            <div className="truncate text-[12px] font-semibold text-[var(--color-fg)]">
              Quiver Bioscience
            </div>
            <div className="text-[10.5px] text-[var(--color-fg-faint)]">
              Principal workspace
            </div>
          </div>
          <Settings className="size-3.5 text-[var(--color-fg-faint)]" />
        </div>
      </div>
    </div>
  );
}

function HistoryItem({
  conv,
  active,
  onOpen,
}: {
  conv: Conversation;
  active: boolean;
  onOpen: () => void;
}) {
  const rename = useFirm((s) => s.renameConversation);
  const star = useFirm((s) => s.starConversation);
  const remove = useFirm((s) => s.removeConversation);
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState(conv.title ?? "");

  const commit = () => {
    setEditing(false);
    const t = draft.trim();
    if (t && t !== conv.title) rename(conv.id, t);
    else setDraft(conv.title ?? "");
  };

  return (
    <div
      className={cn(
        "group relative rounded-[var(--radius-sm)] transition-colors",
        active ? "bg-[var(--color-accent-soft)]" : "hover:bg-[var(--color-bg-subtle)]",
      )}
    >
      <button
        onClick={onOpen}
        className="flex w-full flex-col items-start gap-0.5 px-2.5 py-2 text-left"
      >
        {editing ? (
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              if (e.key === "Enter") commit();
              if (e.key === "Escape") {
                setEditing(false);
                setDraft(conv.title ?? "");
              }
            }}
            className="w-full rounded-[4px] border border-[var(--color-accent)] bg-[var(--color-panel)] px-1 py-0.5 text-[12.5px] text-[var(--color-fg)] outline-none"
          />
        ) : (
          <div className="flex w-full items-center gap-1">
            {conv.starred && (
              <Star className="size-2.5 shrink-0 fill-[var(--color-warn)] text-[var(--color-warn)]" />
            )}
            <span
              className={cn(
                "truncate text-[12.5px] font-medium",
                active ? "text-[var(--color-accent)]" : "text-[var(--color-fg)]",
              )}
            >
              {conv.title || "Untitled"}
            </span>
          </div>
        )}
        {conv.preview && !editing && (
          <p className="truncate text-[10.5px] text-[var(--color-fg-faint)]">
            {conv.preview}
          </p>
        )}
        {conv.updated_at && !editing && (
          <span className="text-[10px] text-[var(--color-fg-faint)]">
            {relTime(conv.updated_at)}
          </span>
        )}
      </button>

      <div className="absolute right-1 top-1.5 opacity-0 transition-opacity group-hover:opacity-100">
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              className="flex size-6 items-center justify-center rounded-[4px] text-[var(--color-fg-subtle)] hover:bg-[var(--color-surface3)] hover:text-[var(--color-fg)]"
              onClick={(e) => e.stopPropagation()}
              aria-label="Analysis actions"
            >
              <MoreHorizontal className="size-3.5" />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={4}
              className="z-50 min-w-[150px] overflow-hidden rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-panel)] p-1 shadow-[0_8px_28px_rgba(0,0,0,0.14)] fadein"
            >
              <MenuItem
                icon={<Pencil className="size-3.5" />}
                label="Rename"
                onSelect={() => setEditing(true)}
              />
              <MenuItem
                icon={
                  <Star
                    className={cn(
                      "size-3.5",
                      conv.starred && "fill-[var(--color-warn)] text-[var(--color-warn)]",
                    )}
                  />
                }
                label={conv.starred ? "Unstar" : "Star"}
                onSelect={() => star(conv.id, !conv.starred)}
              />
              <DropdownMenu.Separator className="my-1 h-px bg-[var(--color-border)]" />
              <MenuItem
                icon={<Trash2 className="size-3.5" />}
                label="Delete"
                danger
                onSelect={() => remove(conv.id)}
              />
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </div>
  );
}

function MenuItem({
  icon,
  label,
  onSelect,
  danger,
}: {
  icon: React.ReactNode;
  label: string;
  onSelect: () => void;
  danger?: boolean;
}) {
  return (
    <DropdownMenu.Item
      onSelect={onSelect}
      className={cn(
        "flex cursor-pointer items-center gap-2 rounded-[var(--radius-sm)] px-2 py-1.5 text-[12.5px] outline-none transition-colors data-[highlighted]:bg-[var(--color-bg-subtle)]",
        danger
          ? "text-[var(--color-danger)]"
          : "text-[var(--color-fg-muted)] data-[highlighted]:text-[var(--color-fg)]",
      )}
    >
      {icon}
      {label}
    </DropdownMenu.Item>
  );
}
