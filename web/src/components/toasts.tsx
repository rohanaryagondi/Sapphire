"use client";
/* ============================================================================
   Phase 5 — run notifications (toasts).
   Event-driven off the run lifecycle in store.ts; survives navigation away
   because this component is mounted at the root (page.tsx) and the store is
   global.  Zero emojis — lucide-react SVG icons only.
   ============================================================================ */
import * as React from "react";
import { CheckCircle, Loader, XCircle, X, Info } from "lucide-react";
import { useFirm } from "@/lib/store";
import type { NotificationKind } from "@/lib/store";
import { cn } from "@/lib/utils";

const ICON: Record<NotificationKind, React.ReactNode> = {
  info: <Info className="size-4 shrink-0 text-[var(--color-fg-subtle)]" />,
  running: <Loader className="size-4 shrink-0 animate-spin text-[var(--color-accent)]" />,
  complete: <CheckCircle className="size-4 shrink-0 text-[var(--color-ok)]" />,
  error: <XCircle className="size-4 shrink-0 text-[var(--color-danger)]" />,
};

const KIND_BORDER: Record<NotificationKind, string> = {
  info: "border-[var(--color-border-strong)]",
  running: "border-[var(--color-accent)]/40",
  complete: "border-[var(--color-ok)]/40",
  error: "border-[var(--color-danger)]/40",
};

export function ToastContainer() {
  const notifications = useFirm((s) => s.notifications);
  const dismiss = useFirm((s) => s.dismissNotification);

  if (notifications.length === 0) return null;

  return (
    <div
      aria-live="polite"
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-5 right-5 z-[200] flex flex-col-reverse gap-2"
    >
      {notifications.map((n) => (
        <Toast key={n.id} id={n.id} kind={n.kind} title={n.title} body={n.body} onDismiss={dismiss} />
      ))}
    </div>
  );
}

function Toast({
  id,
  kind,
  title,
  body,
  onDismiss,
}: {
  id: string;
  kind: NotificationKind;
  title: string;
  body?: string;
  onDismiss: (id: string) => void;
}) {
  return (
    <div
      role="status"
      data-kind={kind}
      className={cn(
        "pointer-events-auto flex min-w-[260px] max-w-[340px] items-start gap-3 rounded-[var(--radius-lg)] border bg-[var(--color-panel-raised)] px-3.5 py-3 shadow-[0_8px_32px_rgba(0,0,0,0.55)] fadein",
        KIND_BORDER[kind],
      )}
    >
      {ICON[kind]}
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-[var(--color-fg)]">{title}</p>
        {body && (
          <p className="mt-0.5 truncate text-[11.5px] text-[var(--color-fg-subtle)]">{body}</p>
        )}
      </div>
      <button
        onClick={() => onDismiss(id)}
        aria-label="Dismiss notification"
        className="shrink-0 rounded-[4px] p-0.5 text-[var(--color-fg-faint)] hover:text-[var(--color-fg)] focus:outline-none"
      >
        <X className="size-3.5" />
      </button>
    </div>
  );
}
