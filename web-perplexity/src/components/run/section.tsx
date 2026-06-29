"use client";
import * as React from "react";

/** A Perplexity-style section header: label · hairline divider · count pill. */
export function SectionHeader({
  label,
  count,
  right,
}: {
  label: string;
  count?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="mb-3 mt-6 flex items-center gap-2.5">
      <span className="text-[10px] font-bold uppercase tracking-[0.07em] text-[var(--color-fg-faint)]">
        {label}
      </span>
      <span className="h-px flex-1 bg-[var(--color-border-light)]" />
      {count && (
        <span className="rounded-full border border-[var(--color-border)] bg-[var(--color-bg-subtle)] px-2 py-0.5 text-[10px] font-medium text-[var(--color-fg-subtle)]">
          {count}
        </span>
      )}
      {right}
    </div>
  );
}
