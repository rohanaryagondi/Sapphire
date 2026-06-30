"use client";
/* ============================================================================
   SideChat — WO-8 Phase 3. The scoped side-chat mounted at the bottom of the
   Info tab: a chat bar + a few suggested questions + a conversation view once
   a question has been asked. Answers come ONLY from the `facts` prop (the
   selected step's contributed facts / cited dossier entries) via
   `askScoped()` (web/src/lib/api.ts → POST /api/step-chat →
   sapphire-orchestrator/scoped_chat.py) — never the whole dossier.

   `‹ detail` clears the conversation and returns to the suggested-questions +
   input view (simple local component state; no store changes).
   ============================================================================ */
import { useEffect, useRef, useState } from "react";
import { ChevronLeft, Send } from "lucide-react";
import { askScoped } from "@/lib/api";
import type { Fact } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Message {
  q: string;
  a: string;
  pending?: boolean;
}

const SUGGESTED = ["What's the strongest fact here?", "Any caveats or uncertainty?"];

export function SideChat({
  scopeLabel,
  facts,
  agentId,
  prefill,
  onPrefillConsumed,
}: {
  scopeLabel: string;
  /** ONLY the selected step's facts — never the whole dossier. SideChat never
   *  widens this; it forwards exactly this list to askScoped(). */
  facts: Fact[];
  agentId?: string;
  /** set by a FactCard's "ask" button (via the parent Info view) to pre-fill
   *  the input scoped to that one fact. */
  prefill?: string;
  onPrefillConsumed?: () => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!prefill) return;
    setInput(prefill);
    inputRef.current?.focus();
    onPrefillConsumed?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill]);

  const send = async (question: string) => {
    const q = question.trim();
    if (!q) return;
    setInput("");
    setMessages((m) => [...m, { q, a: "…", pending: true }]);
    const answer = await askScoped(q, facts, agentId);
    setMessages((m) => {
      const next = [...m];
      const last = next[next.length - 1];
      if (last && last.q === q && last.pending) {
        next[next.length - 1] = { q, a: answer };
      } else {
        next.push({ q, a: answer });
      }
      return next;
    });
  };

  const inConversation = messages.length > 0;

  return (
    <div className="shrink-0 border-t border-[var(--color-border)]">
      {inConversation && (
        <>
          <div className="flex items-center gap-2 px-3 py-1.5 text-[10.5px] text-[var(--color-fg-subtle)]">
            <span className="size-1.5 shrink-0 rounded-full bg-[var(--color-q)]" />
            <span>
              chatting about · <b className="text-[var(--color-fg-muted)]">{scopeLabel}</b>
            </span>
            <span className="flex-1" />
            <button
              onClick={() => setMessages([])}
              className="flex items-center gap-0.5 rounded-[5px] px-1.5 py-0.5 text-[10.5px] text-[var(--color-fg-subtle)] transition-colors hover:bg-[var(--color-elevated)] hover:text-[var(--color-fg)]"
            >
              <ChevronLeft className="size-3" /> detail
            </button>
          </div>
          <div className="max-h-[220px] space-y-2 overflow-y-auto px-3 pb-2">
            {messages.map((m, i) => (
              <div key={i} className="space-y-1">
                <div className="rounded-[7px] bg-[var(--color-elevated)] px-2.5 py-1.5 text-[12px] text-[var(--color-fg)]">
                  {m.q}
                </div>
                <div
                  className={cn(
                    "rounded-[7px] border border-[var(--color-q-bd)] bg-[var(--color-q-soft)] px-2.5 py-1.5 text-[12px] leading-relaxed text-[#efeaff]",
                    m.pending && "italic text-[var(--color-fg-faint)]",
                  )}
                >
                  {m.a}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {!inConversation && (
        <div className="flex flex-wrap gap-1.5 px-3 pt-2">
          {SUGGESTED.map((q) => (
            <button
              key={q}
              onClick={() => send(q)}
              className="rounded-[6px] border border-[var(--color-border)] px-2 py-1 text-[11px] text-[var(--color-fg-muted)] transition-colors hover:border-[var(--color-q-bd)] hover:text-[var(--color-q-text)]"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-1.5 p-2.5">
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") send(input);
          }}
          placeholder={inConversation ? "ask a follow-up…" : `ask about ${scopeLabel}…`}
          className="h-8 min-w-0 flex-1 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2.5 text-[12.5px] text-[var(--color-fg)] outline-none placeholder:text-[var(--color-fg-faint)] focus:border-[var(--color-q-bd)]"
        />
        <button
          onClick={() => send(input)}
          disabled={!input.trim()}
          aria-label="Send"
          className="flex size-8 shrink-0 items-center justify-center rounded-[var(--radius-sm)] bg-[var(--color-q)] text-white transition-opacity disabled:opacity-40"
        >
          <Send className="size-3.5" />
        </button>
      </div>
    </div>
  );
}
