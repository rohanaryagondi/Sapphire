"use client";
import * as React from "react";
import { ArrowUp, Loader2, Sparkles } from "lucide-react";
import { useFirm } from "@/lib/store";
import { cn } from "@/lib/utils";

export function Composer() {
  const [text, setText] = React.useState("");
  const taRef = React.useRef<HTMLTextAreaElement>(null);
  const running = useFirm((s) => s.running);
  const profile = useFirm((s) => s.profile);
  const submit = useFirm((s) => s.submit);

  const canSend = (text.trim().length > 0 || profile === "replay") && !running;

  const autosize = React.useCallback(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 180) + "px";
  }, []);

  const send = () => {
    if (!canSend) return;
    const q = text;
    setText("");
    requestAnimationFrame(autosize);
    submit(q);
  };

  React.useEffect(() => {
    const handler = (e: Event) => {
      const q = (e as CustomEvent<string>).detail;
      setText(q);
      taRef.current?.focus();
      requestAnimationFrame(autosize);
    };
    window.addEventListener("sapphire:fill", handler as EventListener);
    return () => window.removeEventListener("sapphire:fill", handler as EventListener);
  }, [autosize]);

  return (
    <div className="shrink-0 border-t border-[var(--color-border)] bg-[var(--color-panel)] px-5 py-3">
      <div className="mx-auto max-w-[820px]">
        <div className="flex items-end gap-2 rounded-[12px] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-3 py-2.5 transition-all duration-150 focus-within:border-[var(--color-accent)] focus-within:bg-[var(--color-panel)] focus-within:shadow-[0_0_0_3px_var(--color-accent-soft)]">
          <textarea
            ref={taRef}
            value={text}
            rows={1}
            onChange={(e) => {
              setText(e.target.value);
              autosize();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            placeholder={
              profile === "replay"
                ? "Replay a frozen capture, or type to override…"
                : "Ask a CNS target / diligence question…"
            }
            className="max-h-[180px] flex-1 resize-none bg-transparent text-[13.5px] leading-relaxed text-[var(--color-fg)] outline-none placeholder:text-[var(--color-fg-faint)]"
          />
          <button
            onClick={send}
            disabled={!canSend}
            aria-label="Convene the firm"
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-[var(--radius-sm)] transition-all duration-150",
              canSend
                ? "bg-[var(--color-fg)] text-white hover:bg-[#000]"
                : "cursor-not-allowed bg-[var(--color-surface3)] text-[var(--color-fg-faint)]",
            )}
          >
            {running ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ArrowUp className="size-4" />
            )}
          </button>
        </div>
        <div className="mt-1.5 flex items-center justify-between px-1 text-[10.5px] text-[var(--color-fg-faint)]">
          <span className="flex items-center gap-1">
            <Sparkles className="size-3" />
            22 agents · Bucket 1 → Bucket 2 · <strong className="font-semibold text-[var(--color-fg-subtle)]">claude</strong> under the hood
          </span>
          <span>Sapphire never fabricates — unknowns are flagged, not faked.</span>
        </div>
      </div>
    </div>
  );
}
