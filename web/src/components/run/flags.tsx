"use client";
import { useState } from "react";
import { AlertTriangle, Ban, ChevronRight, HelpCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DiscoverFlags } from "@/lib/types";

/**
 * Collapsible callout for VETO, DIVERGENCE, or KNOWN_UNKNOWNS.
 * Default COLLAPSED — click the header to expand.
 * Mirrors the CollapseToggle + border pattern from dossier.tsx.
 */
function Callout({
  tone,
  icon,
  title,
  items,
}: {
  tone: "veto" | "divergence" | "unknown";
  icon: React.ReactNode;
  title: string;
  items: string[];
}) {
  const [open, setOpen] = useState(false);

  const ring =
    tone === "veto"
      ? "border-[rgba(248,81,73,0.32)] bg-[rgba(248,81,73,0.06)]"
      : tone === "divergence"
        ? "border-[rgba(210,153,34,0.30)] bg-[rgba(210,153,34,0.06)]"
        : "border-[var(--color-border)] bg-[var(--color-bg-subtle)]";
  const head =
    tone === "veto"
      ? "text-[#ff7b72]"
      : tone === "divergence"
        ? "text-[#e3b341]"
        : "text-[var(--color-fg-muted)]";

  return (
    <div className={`rounded-[var(--radius)] border p-3 ${ring}`}>
      {/* Clickable header with count + chevron */}
      <button
        data-testid={`flags-toggle-${tone}`}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 text-left"
      >
        <span className={`flex items-center gap-1.5 flex-1 text-[12px] font-medium ${head}`}>
          {icon}
          {title} ({items.length})
        </span>
        <ChevronRight
          className={cn(
            "size-3.5 shrink-0 transition-transform duration-150",
            head,
            open && "rotate-90",
          )}
        />
      </button>

      {/* Expanded item list */}
      {open && (
        <ul className="mt-2 space-y-1 pl-0.5" data-testid={`flags-body-${tone}`}>
          {items.map((it, i) => (
            <li
              key={i}
              className="flex gap-1.5 text-[12.5px] leading-snug text-[var(--color-fg-muted)]"
            >
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-current opacity-50" />
              <span>{it}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Flags({ flags }: { flags?: DiscoverFlags }) {
  if (!flags) return null;
  const veto = flags.VETO ?? [];
  const div = flags.DIVERGENCE ?? [];
  const ku = flags.KNOWN_UNKNOWNS ?? [];
  if (!veto.length && !div.length && !ku.length) return null;
  return (
    <div className="space-y-2">
      {veto.length > 0 && (
        <Callout
          tone="veto"
          icon={<Ban className="size-3.5" />}
          title="VETO — the roundtable adjudicates"
          items={veto}
        />
      )}
      {div.length > 0 && (
        <Callout
          tone="divergence"
          icon={<AlertTriangle className="size-3.5" />}
          title="DIVERGENCE — internal vs external"
          items={div}
        />
      )}
      {ku.length > 0 && (
        <Callout
          tone="unknown"
          icon={<HelpCircle className="size-3.5" />}
          title="Known unknowns — flagged, not faked"
          items={ku}
        />
      )}
    </div>
  );
}
