"use client";
import * as React from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Check, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
  hint?: string;
  dot?: string; // a tailwind/arbitrary color class for a leading dot
}

export function Select({
  value,
  options,
  onChange,
  label,
  className,
}: {
  value: string;
  options: SelectOption[];
  onChange: (v: string) => void;
  label?: string;
  className?: string;
}) {
  const current = options.find((o) => o.value === value) ?? options[0];
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className={cn(
            "group inline-flex h-8 items-center gap-1.5 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-elevated)] px-2.5 text-[13px] text-[var(--color-fg)] outline-none transition-colors hover:border-[var(--color-border-strong)] focus-visible:ring-2 focus-visible:ring-[var(--color-accent-ring)] data-[state=open]:border-[var(--color-border-strong)]",
            className,
          )}
        >
          {label && (
            <span className="text-[11px] text-[var(--color-fg-subtle)]">{label}</span>
          )}
          {current?.dot && (
            <span className={cn("h-1.5 w-1.5 rounded-full", current.dot)} />
          )}
          <span className="font-medium">{current?.label}</span>
          <ChevronsUpDown className="size-3 text-[var(--color-fg-subtle)]" />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          className="z-50 min-w-[200px] overflow-hidden rounded-[var(--radius)] border border-[var(--color-border-strong)] bg-[var(--color-panel-raised)] p-1 shadow-[0_12px_40px_rgba(0,0,0,0.55)] fadein"
        >
          {options.map((o) => (
            <DropdownMenu.Item
              key={o.value}
              onSelect={() => onChange(o.value)}
              className="flex cursor-pointer items-center gap-2 rounded-[var(--radius-sm)] px-2 py-1.5 text-[13px] text-[var(--color-fg-muted)] outline-none transition-colors data-[highlighted]:bg-[var(--color-elevated)] data-[highlighted]:text-[var(--color-fg)]"
            >
              {o.dot && <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", o.dot)} />}
              <div className="flex flex-1 flex-col">
                <span className="font-medium leading-tight">{o.label}</span>
                {o.hint && (
                  <span className="text-[11px] leading-tight text-[var(--color-fg-subtle)]">
                    {o.hint}
                  </span>
                )}
              </div>
              {o.value === value && (
                <Check className="size-3.5 text-[var(--color-accent)]" />
              )}
            </DropdownMenu.Item>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
