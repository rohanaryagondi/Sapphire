# Sapphire — Vision

*The north star. What Sapphire is, why it exists, and the principles that don't bend. For the current state of
the build see [`status/OVERALL.md`](../status/OVERALL.md); for the end-to-end design see
[`ARCHITECTURE.md`](ARCHITECTURE.md).*

## One sentence
**Sapphire is an agentic CNS drug-discovery decision system** — a user-facing orchestrator that runs a
two-bucket "firm" of AI agents to turn a hard CNS question into a cited fact dossier plus a panel of expert
judgments, and writes the report.

## Why it exists
CNS drug discovery decisions are made under deep uncertainty, across many incommensurable lenses — biology,
regulatory history, IP, payer, safety, manufacturing, clinical, financial, reputational. A human decision
team integrates all of that slowly and unevenly. Sapphire's bet: an orchestrated firm of specialized agents
can **gather the facts exhaustively, surface the disagreements honestly, and show its work** — faster than a
committee and more transparently than a single model. The goal is not to *replace* the decision; it is to put
a complete, cited, multi-perspective picture in front of the people who make it.

## The firm (two buckets)
1. **Bucket 1 — Facts (junior analysts).** Gather a *cited fact dossier* from EMET (BenchSci, live),
   Q-Models (the model launchpad), the Quiver internal moat, and the semantic web agents. Iterate until the
   dossier is complete — contradiction, gap, and veto checks — not one pass.
2. **Bucket 2 — Deliberation (partners).** A roundtable of company + institutional persona agents debate the
   dossier: independent verdicts, then a moderated rebuttal round. **No forced consensus — the spread is the
   product.** A clean disagreement between a regulator's lens and a KOL's lens is signal, not noise.
3. **Synthesis.** The orchestrator writes the report: the facts, and how each player reacted.

## What "good" looks like
- Handle the ~300 hard CNS questions in James' Feb-2026 corpus — and harder ones — end to end.
- Every claim in a dossier is **cited and provenance-labeled**; every opinion in the roundtable **cites the
  dossier** (partners never invent facts — they file a fact-request).
- A user can see *why*: the plan, the evidence with its source tier, the flags (veto / divergence / unknown),
  and each persona's verdict with its reasoning.

## Principles that don't bend
- **Facts vs. judgment.** Bucket 1 is cited facts only; Bucket 2 is opinion that cites those facts.
- **The spread is the product.** No forced consensus. Surface dissent; don't average it away.
- **Internal↔external contradictions are `DIVERGENCE`, not errors.** Often that gap is the alpha — Quiver sees
  what the literature can't. Surface it; never auto-reconcile.
- **Veto facts are gates, not silent kills.** FDA institutional memory and IP can gate a program; the
  roundtable adjudicates them in the open.
- **The data boundary is absolute.** Quiver internal EP/CRISPR data and scores never leave to EMET / web /
  Q-Models. Public identifiers only (gene symbols, SMILES, disease terms, PMIDs).
- **Empirical culture — "SOTA on shit is still shit."** Mark `proven` vs `paper-claim`. Never oversell a mock
  or a benchmark. Provenance is enforced mechanically, not by trust.
- **Honesty over optimism.** A green test suite is a claim, not a proof; we verify behavior and report
  failures plainly. (This is also why the *build* harness exists — see `dev/`.)

## Where it's going (direction, not a dated plan)
- **Real tools, plugged into the orchestrator scaffold.** Per the 2026-06 sprint direction, Loka provides the
  front-end/orchestrator scaffold; Quiver's tools plug into it: OPAL, ASO Design, ASO toxicity (live),
  chronic-tox (roadmap), Experiment Design. Sapphire is the firm that *calls* these tools as fact sources.
- **Live everywhere it claims to be live.** EMET and personas are live; Q-Models real; the internal moat real;
  ASO-tox real. The standing work is to retire every remaining mock honestly and wire the live path
  (`live_engine.run_live`) to the front door.
- **Breadth and depth of the dossier.** More semantic agents, richer divergence detection, broader scenario
  coverage — so the firm can take on the hardest questions, not just the representative ones.

## How we build it
Three contributors (rohan · hayes · gavin), each driving their own Claude, through the **dev harness**
(`dev/`): plan → implement → independent review → functional verification → PR → Rohan's Claude approves and
merges. The build discipline mirrors the product philosophy — cited, verified, honest. See
[`status/OVERALL.md`](../status/OVERALL.md) for where we are and [`status/WORKBOARD.md`](../status/WORKBOARD.md)
for who is building what.
