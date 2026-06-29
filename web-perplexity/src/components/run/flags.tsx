"use client";
import { AlertTriangle, Ban, HelpCircle } from "lucide-react";
import type { DiscoverFlags } from "@/lib/types";

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
  const ring =
    tone === "veto"
      ? "border-[#fca5a5] bg-[var(--color-danger-bg)]"
      : tone === "divergence"
        ? "border-[#fcd34d] bg-[var(--color-warn-bg)]"
        : "border-[var(--color-border)] bg-[var(--color-bg-subtle)]";
  const head =
    tone === "veto"
      ? "text-[var(--color-danger)]"
      : tone === "divergence"
        ? "text-[var(--color-warn)]"
        : "text-[var(--color-fg-muted)]";
  return (
    <div className={`rounded-[var(--radius)] border p-3 ${ring}`}>
      <div className={`mb-1.5 flex items-center gap-1.5 text-[12px] font-semibold ${head}`}>
        {icon}
        {title}
      </div>
      <ul className="space-y-1 pl-0.5">
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
          title="VETO — the roundtable adjudicates (never a silent kill)"
          items={veto}
        />
      )}
      {div.length > 0 && (
        <Callout
          tone="divergence"
          icon={<AlertTriangle className="size-3.5" />}
          title="DIVERGENCE — internal vs external, surfaced not reconciled (often the alpha)"
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
