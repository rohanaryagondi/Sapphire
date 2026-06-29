"use client";
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-[var(--radius-sm)] text-[13px] font-medium transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-ring)] disabled:pointer-events-none disabled:opacity-45 select-none [&_svg]:size-3.5 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--color-accent)] text-white shadow-[0_1px_2px_rgba(0,0,0,0.4),inset_0_1px_0_rgba(255,255,255,0.12)] hover:bg-[var(--color-accent-hover)]",
        secondary:
          "bg-[var(--color-elevated)] text-[var(--color-fg)] border border-[var(--color-border)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-panel-raised)]",
        ghost:
          "text-[var(--color-fg-muted)] hover:text-[var(--color-fg)] hover:bg-[var(--color-elevated)]",
        outline:
          "border border-[var(--color-border)] text-[var(--color-fg-muted)] hover:text-[var(--color-fg)] hover:border-[var(--color-border-strong)] hover:bg-[var(--color-bg-subtle)]",
        danger:
          "bg-transparent text-[var(--color-danger)] hover:bg-[rgba(248,81,73,0.10)]",
      },
      size: {
        sm: "h-7 px-2.5",
        default: "h-8 px-3",
        lg: "h-9 px-4 text-sm",
        icon: "h-7 w-7 p-0",
        "icon-sm": "h-6 w-6 p-0 [&_svg]:size-3",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(buttonVariants({ variant, size }), className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
