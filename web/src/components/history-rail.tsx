"use client";
import * as React from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import * as Dialog from "@radix-ui/react-dialog";
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
  const [confirmOpen, setConfirmOpen] = React.useState(false);
  // guards a double fire: pressing Enter commits, which then blurs the input and
  // would otherwise commit a second time (#5).
  const settledRef = React.useRef(false);

  const startEdit = () => {
    setDraft(conv.title ?? "");
    settledRef.current = false;
    setEditing(true);
  };
  const commit = () => {
    if (settledRef.current) return;
    settledRef.current = true;
    setEditing(false);
    const t = draft.trim();
    if (t && t !== (conv.title ?? "")) rename(conv.id, t);
    else setDraft(conv.title ?? "");
  };
  const cancel = () => {
    settledRef.current = true;
    setEditing(false);
    setDraft(conv.title ?? "");
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

      {editing ? (
        /* the edit field is a SIBLING of the row button (never nested inside it),
           so Enter/blur/Escape behave predictably (#5). Enter commits, blur
           commits, Escape cancels. */
        <div className="px-2.5 py-2">
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={commit}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                commit();
              } else if (e.key === "Escape") {
                e.preventDefault();
                cancel();
              }
            }}
            className="w-full rounded-[4px] border border-[var(--color-border-focus)] bg-[var(--color-bg)] px-1 py-0.5 text-[12.5px] text-[var(--color-fg)] outline-none"
          />
        </div>
      ) : (
        <button
          onClick={onOpen}
          className="flex w-full items-start gap-2 px-2.5 py-2 text-left"
        >
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1">
              {conv.starred && (
                <Star className="size-2.5 shrink-0 fill-[var(--color-warn)] text-[var(--color-warn)]" />
              )}
              <span className="truncate text-[12.5px] font-medium text-[var(--color-fg)]">
                {conv.title || "Untitled"}
              </span>
            </div>
            {conv.preview && (
              <p className="mt-0.5 truncate text-[11px] text-[var(--color-fg-subtle)]">
                {conv.preview}
              </p>
            )}
            {conv.updated_at && (
              <span className="text-[10px] text-[var(--color-fg-faint)]">
                {relTime(conv.updated_at)}
              </span>
            )}
          </div>
        </button>
      )}

      {/* actions */}
      {!editing && (
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
                  onSelect={() => startEdit()}
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
                  onSelect={() => setConfirmOpen(true)}
                />
              </DropdownMenu.Content>
            </DropdownMenu.Portal>
          </DropdownMenu.Root>
        </div>
      )}

      {/* #9 — delete confirmation (no silent permanent delete) */}
      <DeleteConfirm
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={conv.title || "Untitled"}
        onConfirm={() => {
          setConfirmOpen(false);
          remove(conv.id);
        }}
      />
    </div>
  );
}

function DeleteConfirm({
  open,
  onOpenChange,
  title,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  title: string;
  onConfirm: () => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[99] bg-black/55 backdrop-blur-sm fadein" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-[100] w-[min(380px,92vw)] -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-panel-raised)] p-4 shadow-[0_24px_80px_rgba(0,0,0,0.65)] fadein">
          <Dialog.Title className="text-[14px] font-semibold text-[var(--color-fg)]">
            Delete conversation?
          </Dialog.Title>
          <Dialog.Description className="mt-1.5 text-[12.5px] leading-relaxed text-[var(--color-fg-muted)]">
            “{title}” will be permanently deleted. This can’t be undone.
          </Dialog.Description>
          <div className="mt-4 flex justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="ghost" size="sm" className="h-7">
                Cancel
              </Button>
            </Dialog.Close>
            <Button
              variant="default"
              size="sm"
              onClick={onConfirm}
              className="h-7 bg-[var(--color-danger)] text-white hover:bg-[var(--color-danger)]/90"
            >
              <Trash2 className="size-3.5" />
              Delete
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
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
