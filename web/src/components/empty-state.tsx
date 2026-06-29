"use client";
import { ArrowUpRight, Dna, FlaskConical, Microscope, Users } from "lucide-react";

const SUGGESTIONS = [
  {
    q: "Which genes rescue the TSC2 phenotype the most?",
    tag: "Target rescue",
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

export function EmptyState() {
  return (
    <div className="dot-grid flex h-full flex-col items-center justify-center px-6">
      <div className="w-full max-w-2xl fadeup">
        <div className="mb-6 flex flex-col items-center text-center">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-[14px] bg-gradient-to-br from-[#5b8def] to-[#7c5cff] shadow-[0_0_0_1px_rgba(255,255,255,0.10),0_8px_30px_-6px_rgba(77,141,255,0.55)]">
            <svg viewBox="0 0 24 24" className="h-6 w-6 text-white" fill="none">
              <path
                d="M12 2 4 8l8 14 8-14-8-6Z"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinejoin="round"
              />
              <path d="M4 8h16M12 2v20" stroke="currentColor" strokeWidth="1" opacity="0.6" />
            </svg>
          </div>
          <h1 className="text-[22px] font-semibold tracking-tight text-[var(--color-fg)]">
            Convene the firm
          </h1>
          <p className="mt-1.5 max-w-md text-[13.5px] leading-relaxed text-[var(--color-fg-muted)]">
            Ask a hard CNS question. Sapphire gathers a{" "}
            <span className="text-[var(--color-internal)]">cited fact dossier</span>, runs a{" "}
            <span className="text-[var(--color-external)]">persona roundtable</span>, and writes a
            synthesis — with every fact labeled by tier, provenance, and data plane.
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
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-elevated)] text-[var(--color-accent)]">
                  <Icon className="size-3.5" />
                </div>
                <div className="flex-1">
                  <div className="mb-0.5 text-[10.5px] font-medium uppercase tracking-[0.06em] text-[var(--color-fg-subtle)]">
                    {s.tag}
                  </div>
                  <div className="text-[13px] leading-snug text-[var(--color-fg)]">{s.q}</div>
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
