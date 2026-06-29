"use client";
import * as React from "react";
import { cn, provKind, provMarker, tierClass, type ProvKind } from "@/lib/utils";
import type { FlagKind, Plane } from "@/lib/types";

const base =
  "inline-flex items-center gap-1 rounded-[4px] border px-1.5 h-[18px] text-[10px] font-medium leading-none tracking-tight whitespace-nowrap";

/* ── provenance chip (honesty marker — ● REAL / 🧪 simulated / ◆ CAPTURED) ── */
const provStyle: Record<ProvKind, string> = {
  real: "border-[#a7e3c0] bg-[var(--color-ok-bg)] text-[var(--color-ok)]",
  sim: "border-[#fcd34d] bg-[var(--color-warn-bg)] text-[var(--color-warn)]",
  cap: "border-[var(--color-external-border)] bg-[var(--color-external-bg)] text-[var(--color-external)]",
};

export function ProvChip({ prov, via }: { prov?: string; via?: string }) {
  if (!prov) return null;
  const kind = provKind(prov, via);
  return (
    <span className={cn(base, "font-mono", provStyle[kind])} title={`provenance: ${prov}`}>
      <span className="text-[8px] leading-none">{provMarker(kind)}</span>
      {prov}
    </span>
  );
}

/* ── tier chip ──────────────────────────────────────────────────────────── */
const tierStyle: Record<string, string> = {
  T1: "border-[#a7e3c0] bg-[var(--color-ok-bg)] text-[var(--color-ok)]",
  T2: "border-[var(--color-external-border)] bg-[var(--color-external-bg)] text-[var(--color-external)]",
  T3: "border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)]",
};

export function TierChip({ tier }: { tier?: string }) {
  const t = tierClass(tier);
  if (!t) return null;
  return <span className={cn(base, "font-mono font-bold", tierStyle[t])}>{t}</span>;
}

/* ── plane chip — 🔒 internal / 🌐 external ─────────────────────────────── */
export function PlaneChip({ plane }: { plane?: Plane }) {
  const internal = plane === "internal";
  return (
    <span
      className={cn(
        base,
        internal
          ? "border-[var(--color-internal-border)] bg-[var(--color-internal-bg)] text-[var(--color-internal)]"
          : "border-[var(--color-external-border)] bg-[var(--color-external-bg)] text-[var(--color-external)]",
      )}
    >
      {internal ? "🔒 internal" : "🌐 external"}
    </span>
  );
}

/* ── flag chip — VETO / DIVERGENCE / KNOWN_UNKNOWN ──────────────────────── */
const flagStyle: Record<string, string> = {
  VETO: "border-[#fca5a5] bg-[var(--color-danger-bg)] text-[var(--color-danger)]",
  DIVERGENCE: "border-[#fcd34d] bg-[var(--color-warn-bg)] text-[var(--color-warn)]",
  KNOWN_UNKNOWN: "border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)]",
};
const flagIcon: Record<string, string> = {
  VETO: "⛔",
  DIVERGENCE: "⚠",
  KNOWN_UNKNOWN: "?",
};

export function FlagChip({ flag }: { flag?: FlagKind | string }) {
  if (!flag) return null;
  const key = String(flag);
  return (
    <span className={cn(base, "font-semibold", flagStyle[key] ?? flagStyle.KNOWN_UNKNOWN)}>
      <span className="text-[8px]">{flagIcon[key] ?? "•"}</span>
      {key}
    </span>
  );
}

/* ── generic muted chip ─────────────────────────────────────────────────── */
export function Chip({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        base,
        "border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-[var(--color-fg-subtle)]",
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}

/* ── status dot ─────────────────────────────────────────────────────────── */
export function StatusDot({
  status,
  live,
  className,
}: {
  status: "ok" | "abstain" | "running" | "error" | string;
  live?: boolean;
  className?: string;
}) {
  const color =
    status === "ok"
      ? "bg-[var(--color-ok)]"
      : status === "running"
        ? "bg-[var(--color-accent)]"
        : status === "error"
          ? "bg-[var(--color-danger)]"
          : "bg-[var(--color-warn)]";
  return (
    <span
      className={cn(
        "inline-block h-1.5 w-1.5 rounded-full shrink-0",
        color,
        live && "live-dot",
        className,
      )}
    />
  );
}
