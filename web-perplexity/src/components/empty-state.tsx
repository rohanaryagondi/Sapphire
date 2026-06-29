"use client";
import { ArrowUpRight, Dna, FlaskConical, Microscope, Users } from "lucide-react";

const SUGGESTIONS = [
  {
    q: "Which genes rescue the TSC2 phenotype the most?",
    tag: "Gene rescue screen",
    icon: Dna,
  },
  {
    q: "TSC2 in tuberous sclerosis — is it a tractable CNS target?",
    tag: "Diligence",
    icon: Microscope,
  },
  {
    q: "Nav1.8 pain targets — what does the evidence say?",
    tag: "Target validation",
    icon: FlaskConical,
  },
  {
    q: "Assess the regulatory + payer risk for an ASO in a rare CNS disease.",
    tag: "Roundtable",
    icon: Users,
  },
];

function fill(q: string) {
  window.dispatchEvent(new CustomEvent<string>("sapphire:fill", { detail: q }));
}

function Gem({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none">
      <path
        d="M12 2 4 8l8 14 8-14-8-6Z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M4 8h16M12 2v20" stroke="currentColor" strokeWidth="1" opacity="0.5" />
    </svg>
  );
}

export function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6">
      <div className="w-full max-w-[560px] fadeup">
        <div className="mb-7 flex flex-col items-center text-center">
          <div className="mb-4 flex size-14 items-center justify-center rounded-[16px] bg-gradient-to-br from-[#1a73e8] to-[#6d28d9] text-white shadow-[0_8px_28px_-6px_rgba(26,115,232,0.55)]">
            <Gem className="size-7" />
          </div>
          <h1 className="text-[24px] font-bold tracking-tight text-[var(--color-fg)]">
            Ask Sapphire
          </h1>
          <p className="mt-2 max-w-md text-[13.5px] leading-relaxed text-[var(--color-fg-muted)]">
            Run a two-bucket CNS discovery analysis — a{" "}
            <span className="font-medium text-[var(--color-internal)]">cited fact dossier</span>{" "}
            from 22 agents with first-class citations, then a{" "}
            <span className="font-medium text-[var(--color-external)]">persona roundtable</span>{" "}
            with no forced consensus.
          </p>
        </div>

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {SUGGESTIONS.map((s) => {
            const Icon = s.icon;
            return (
              <button
                key={s.q}
                onClick={() => fill(s.q)}
                className="card-hover group flex items-start gap-3 rounded-[var(--radius)] border border-[var(--color-border)] bg-[var(--color-panel)] p-3 text-left"
              >
                <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg-subtle)] text-[var(--color-accent)]">
                  <Icon className="size-3.5" />
                </div>
                <div className="flex-1">
                  <div className="mb-0.5 text-[10px] font-semibold uppercase tracking-[0.06em] text-[var(--color-fg-faint)]">
                    {s.tag}
                  </div>
                  <div className="text-[12.5px] leading-snug text-[var(--color-fg)]">
                    {s.q}
                  </div>
                </div>
                <ArrowUpRight className="size-3.5 shrink-0 text-[var(--color-fg-faint)] transition-colors group-hover:text-[var(--color-accent)]" />
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
