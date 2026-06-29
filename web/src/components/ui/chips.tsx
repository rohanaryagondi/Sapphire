"use client";
import * as React from "react";
import { cn, provKind, provMarker, tierClass, type ProvKind } from "@/lib/utils";
import type { FlagKind, Plane } from "@/lib/types";

const base =
  "inline-flex items-center gap-1 rounded-[5px] border px-1.5 h-[18px] text-[10.5px] font-medium leading-none tracking-tight whitespace-nowrap font-mono";

/* ── provenance chip (honesty marker — ● REAL / 🧪 simulated / ◆ CAPTURED) ── */
const provStyle: Record<ProvKind, string> = {
  real: "border-[rgba(63,185,80,0.30)] bg-[rgba(63,185,80,0.08)] text-[#7ee787]",
  sim: "border-[rgba(210,153,34,0.30)] bg-[rgba(210,153,34,0.08)] text-[#e3b341]",
  cap: "border-[rgba(86,182,255,0.28)] bg-[rgba(86,182,255,0.08)] text-[#79c0ff]",
};

export function ProvChip({ prov, via }: { prov?: string; via?: string }) {
  if (!prov) return null;
  const kind = provKind(prov, via);
  return (
    <span className={cn(base, provStyle[kind])} title={`provenance: ${prov}`}>
      <span className="text-[8px] leading-none">{provMarker(kind)}</span>
      {prov}
    </span>
  );
}

/* ── tier chip ──────────────────────────────────────────────────────────── */
const tierStyle: Record<string, string> = {
  T1: "border-[rgba(77,141,255,0.40)] bg-[rgba(77,141,255,0.12)] text-[#9cc1ff]",
  T2: "border-[rgba(125,133,255,0.32)] bg-[rgba(125,133,255,0.10)] text-[#b3b8ff]",
  T3: "border-[var(--color-border-strong)] bg-[var(--color-elevated)] text-[var(--color-fg-muted)]",
};

export function TierChip({ tier }: { tier?: string }) {
  const t = tierClass(tier);
  if (!t) return null;
  return <span className={cn(base, tierStyle[t])}>{t}</span>;
}

/* ── plane chip — 🔒 internal / 🌐 external ─────────────────────────────── */
export function PlaneChip({ plane }: { plane?: Plane }) {
  const internal = plane === "internal";
  return (
    <span
      className={cn(
        base,
        internal
          ? "border-[rgba(192,132,252,0.32)] bg-[rgba(192,132,252,0.10)] text-[#d6b4fe]"
          : "border-[rgba(86,182,255,0.28)] bg-[rgba(86,182,255,0.08)] text-[#79c0ff]",
      )}
    >
      {internal ? "🔒 internal" : "🌐 external"}
    </span>
  );
}

/* ── flag chip — VETO / DIVERGENCE / KNOWN_UNKNOWN ──────────────────────── */
const flagStyle: Record<string, string> = {
  VETO: "border-[rgba(248,81,73,0.40)] bg-[rgba(248,81,73,0.12)] text-[#ff7b72]",
  DIVERGENCE: "border-[rgba(210,153,34,0.38)] bg-[rgba(210,153,34,0.12)] text-[#e3b341]",
  KNOWN_UNKNOWN: "border-[var(--color-border-strong)] bg-[var(--color-elevated)] text-[var(--color-fg-muted)]",
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
    <span className={cn(base, flagStyle[key] ?? flagStyle.KNOWN_UNKNOWN)}>
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
        "border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-[var(--color-fg-muted)]",
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
