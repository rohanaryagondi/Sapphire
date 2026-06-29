"use client";
import * as React from "react";
import { ArrowUp, Loader2 } from "lucide-react";
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
    ta.style.height = Math.min(ta.scrollHeight, 200) + "px";
  }, []);

  const send = () => {
    if (!canSend) return;
    const q = text;
    setText("");
    requestAnimationFrame(autosize);
    submit(q);
  };

  // allow the empty-state suggestions to fill the box
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
    <div className="border-t border-[var(--color-border)] bg-[color-mix(in_srgb,var(--color-bg)_80%,transparent)] px-4 py-3 backdrop-blur-xl">
      <div className="mx-auto max-w-3xl">
        <div
          className={cn(
            "relative flex items-end gap-2 rounded-[var(--radius-lg)] border border-[var(--color-border-strong)] bg-[var(--color-panel)] px-3 py-2.5 transition-all duration-150 focus-within:border-[var(--color-border-focus)] focus-within:shadow-[0_0_0_3px_var(--color-accent-soft)]",
          )}
        >
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
                : "Ask the firm a CNS target / diligence question…"
            }
            className="max-h-[200px] flex-1 resize-none bg-transparent text-[14px] leading-relaxed text-[var(--color-fg)] outline-none placeholder:text-[var(--color-fg-faint)]"
          />
          <button
            onClick={send}
            disabled={!canSend}
            aria-label="Convene the firm"
            className={cn(
              "flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--radius-sm)] transition-all duration-150",
              canSend
                ? "bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)]"
                : "cursor-not-allowed bg-[var(--color-elevated)] text-[var(--color-fg-faint)]",
            )}
          >
            {running ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : (
              <ArrowUp className="size-3.5" />
            )}
          </button>
        </div>
        <div className="mt-1.5 flex items-center justify-between px-1 text-[11px] text-[var(--color-fg-faint)]">
          <span>
            <span className="kbd">↵</span> send · <span className="kbd">⇧↵</span> newline
          </span>
          <span>Sapphire never fabricates — unknowns are flagged, not faked.</span>
        </div>
      </div>
    </div>
  );
}
