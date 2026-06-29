"use client";
import * as React from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import {
  MessageSquarePlus,
  MoreHorizontal,
  Pencil,
  Search,
  Star,
  Trash2,
} from "lucide-react";
import { useFirm } from "@/lib/store";
import { cn, relTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import type { Conversation } from "@/lib/types";

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
      {/* header */}
      <div className="flex h-11 shrink-0 items-center justify-between gap-2 border-b border-[var(--color-border)] px-3">
        <span className="text-[12px] font-medium uppercase tracking-[0.07em] text-[var(--color-fg-subtle)]">
          History
        </span>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => newChat()}
          disabled={running}
          className="h-7"
        >
          <MessageSquarePlus className="size-3.5" />
          New
        </Button>
      </div>

      {/* search */}
      <div className="shrink-0 px-2.5 py-2">
        <div className="flex items-center gap-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2 focus-within:border-[var(--color-border-focus)]">
          <Search className="size-3 text-[var(--color-fg-faint)]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search conversations…"
            className="h-7 flex-1 bg-transparent text-[12.5px] text-[var(--color-fg)] outline-none placeholder:text-[var(--color-fg-faint)]"
          />
        </div>
      </div>

      {/* list */}
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {filtered.length === 0 ? (
          <div className="px-2 py-8 text-center">
            <p className="text-[12px] leading-relaxed text-[var(--color-fg-subtle)]">
              {available
                ? query
                  ? "No conversations match."
                  : "No conversations yet. Convene the firm to start one."
                : "Conversation history isn't connected yet. Your current session still works — start a new chat."}
            </p>
          </div>
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
        active ? "bg-[var(--color-elevated)]" : "hover:bg-[var(--color-bg-subtle)]",
      )}
    >
      {active && (
        <span className="absolute inset-y-1.5 left-0 w-[2px] rounded-full bg-[var(--color-accent)]" />
      )}
      <button
        onClick={onOpen}
        className="flex w-full items-start gap-2 px-2.5 py-2 text-left"
      >
        <div className="min-w-0 flex-1">
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
              className="w-full rounded-[4px] border border-[var(--color-border-focus)] bg-[var(--color-bg)] px-1 py-0.5 text-[12.5px] text-[var(--color-fg)] outline-none"
            />
          ) : (
            <div className="flex items-center gap-1">
              {conv.starred && (
                <Star className="size-2.5 shrink-0 fill-[var(--color-warn)] text-[var(--color-warn)]" />
              )}
              <span className="truncate text-[12.5px] font-medium text-[var(--color-fg)]">
                {conv.title || "Untitled"}
              </span>
            </div>
          )}
          {conv.preview && !editing && (
            <p className="mt-0.5 truncate text-[11px] text-[var(--color-fg-subtle)]">
              {conv.preview}
            </p>
          )}
          {conv.updated_at && !editing && (
            <span className="text-[10px] text-[var(--color-fg-faint)]">
              {relTime(conv.updated_at)}
            </span>
          )}
        </div>
      </button>

      {/* actions */}
      <div className="absolute right-1 top-1.5 opacity-0 transition-opacity group-hover:opacity-100 data-[open=true]:opacity-100">
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              className="flex size-6 items-center justify-center rounded-[4px] text-[var(--color-fg-subtle)] hover:bg-[var(--color-panel-raised)] hover:text-[var(--color-fg)]"
              onClick={(e) => e.stopPropagation()}
              aria-label="Conversation actions"
            >
              <MoreHorizontal className="size-3.5" />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={4}
              className="z-50 min-w-[150px] overflow-hidden rounded-[var(--radius)] border border-[var(--color-border-strong)] bg-[var(--color-panel-raised)] p-1 shadow-[0_12px_40px_rgba(0,0,0,0.55)] fadein"
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
        "flex cursor-pointer items-center gap-2 rounded-[var(--radius-sm)] px-2 py-1.5 text-[12.5px] outline-none transition-colors data-[highlighted]:bg-[var(--color-elevated)]",
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
