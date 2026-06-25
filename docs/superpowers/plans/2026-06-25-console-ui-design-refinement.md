# Task brief — Sapphire Console UI design refinement (LOKA-native 3-pane)

*Owner: **gavin** (Gavin's Claude iterates the design WITH Gavin; Head Claude reviews/gates any PR). Tier: **Standard**.
Created 2026-06-25. This is **design iteration only** — it does **not** touch the runtime `frontend/` app yet.*

> **⚠ INTERNAL ONLY:** the mockups embed **real internal TSC2 moat values** (consistent with the committed
> `sapphire-orchestrator/scenarios/tsc2_live_run.json`). Treat them as internal design artifacts — don't publish or
> share outside Quiver.

## Context
Head Claude has committed a set of console UI explorations to **`docs/design/console-ui/`** (start at its
[`README.md`](../../design/console-ui/README.md)). The chosen direction is the **★ LOKA-native 3-pane console**
(`docs/design/console-ui/sapphire_loka.html`): the **same running Chainlit app, reorganized** into three panes —
**LEFT** = agent output cards grouped by the two data planes (Internal Vault · External Evidence), **CENTER** = the
response (synthesis verdict + roundtable spread + DIVERGENCE callouts), **RIGHT** = the live harness trace. It reuses
Chainlit's exact shadcn tokens, Quiver purple as `--primary`, the Sapphire gem mark, and Inter — so it reads as the
*same product*, not a new aesthetic. Three earlier explorations (`variant_a` Mission Control, `variant_c` The Firm,
`variant_b` Exec Brief — light) are kept for range, **not** to ship as-is.

## Baseline — the real LOKA-built frontend
The mockups in `docs/design/console-ui/` are the proposed **3-pane (side-panel) evolution** of the **actual running
app** — the **LOKA Chainlit fork at `frontend/`**, re-pointed to the in-process live firm via **`bridge.run →
live_engine.run_live`**. **Run + study that real app first, as the baseline**, before refining the mockups:

```sh
cd frontend && chainlit run main.py --port 8000
# then open http://localhost:8000
```

Three profiles to study: **Demo (mock, instant)** ($0, deterministic — the full process offline), **Live (cheap ·
haiku) (real firm)** (live backends — real moat · real EMET · real seams/Q-Models — with every Claude agent on haiku
so it doesn't burn default-model tokens), and **Replay (captured TSC2)** (a frozen REAL TSC2 run replayed verbatim,
$0, no model/network). **Note:** the **real internal-moat facts require `RohanOnly/moat/moat.sqlite`** present locally
(gitignored) — without it the moat **degrades to empty/mock honestly** (never fabricated, never a crash).

The task is to **evolve that frontend into the agreed 3-pane layout** (left = output cards · center = response · right
= live trace), **staying within LOKA/Chainlit's design tokens** — **not** to replace it with a new app. The fold-in to
`frontend/` happens **only when Gavin signs off**.

## Goal
Iterate the **LOKA-native 3-pane console** **with Gavin** into the agreed design. This is **collaborative design
work**, not a spec to execute blind: **present options, get Gavin's calls, refine** — loop until Gavin signs off.

## The open choices to resolve with Gavin (all inside the LOKA/Chainlit token system)
1. **Trace rail (right):** Step-tree (collapsible plan → agents → personas → synthesis) vs Live-stream (running event
   log). Pick the default; decide whether to keep both (a toggle is mocked).
2. **Density:** comfortable vs compact default; how compact the left cards can get before tier/provenance is illegible.
3. **Left-card grouping:** how the two-plane grouping reads (group headers / divider / color weight) and how each card
   signposts its plane at a glance.
4. **The spread + DIVERGENCE:** how the roundtable spread reads in the center (chips / matrix / per-partner cards) and
   how a `DIVERGENCE` finding is made visually distinct from an ordinary fact.
5. **Signposting the two data planes:** the simplest, strongest visual language for Internal Vault vs External Evidence —
   without ever implying the two are interchangeable.

## How to work
- Iterate **in `docs/design/console-ui/`** — refine `sapphire_loka.html` (and the `README.md` decisions section). You
  may add small alternative mockups in the same dir if it helps present an option, but the deliverable converges on one
  refined `sapphire_loka.html`.
- **Do NOT invent a new aesthetic.** Stay strictly within LOKA/Chainlit's design tokens (the shadcn `--*` variables +
  Quiver purple `--primary`; Inter; the Sapphire gem). The whole point is that it reads as the same running app.
- **Do NOT modify the runtime `frontend/` app.** Folding the agreed design into `frontend/` happens **later**, as a
  separate task, **only when Gavin signals ready**.
- View locally: `python3 -m http.server 8090 --directory docs/design/console-ui` → open `/index.html`.

## Definition of done
- A **refined `docs/design/console-ui/sapphire_loka.html`** that **Gavin signs off on**.
- A **short note of the decisions** made (which way each open choice went) — append to the
  `docs/design/console-ui/README.md` "Open design choices" section (mark each resolved) or a brief `DECISIONS.md`.
- The fold-into-`frontend/` is explicitly **out of scope** here — it's a later task, triggered only when Gavin signals
  the design is ready.

## Constraints (must survive any refinement)
- **Binary-free + self-contained:** brand mark stays an **inline SVG** (Quiver gem recolored to `--primary`), favicon an
  inline `data:` URI. **No committed binary files** (Gate-3 blocks them; `logo_dark.png` already lives in
  `frontend/public/`). Google Fonts (Inter) CDN link is fine (degrades to `system-ui`).
- **Honesty markers preserved** (mirror the product's hard rules): tier + provenance on every fact; the two data planes
  stay visually distinct; **`● live` vs `🧪 simulated` never conflated**; abstentions/tool-failures shown honestly; veto
  reads as a gate, DIVERGENCE reads as surfaced (never auto-reconciled).
- **Real TSC2 data stays internal-only** — the design dir is an internal artifact; don't publish it.
- Stay on the **LOKA/Chainlit token system**; don't invent new colors/type beyond `--primary`.

## Gates
- The usual: **suite stays green** (`bash dev/run-tests.sh` — these are docs/HTML changes, so no engine impact expected,
  but confirm); **Head Claude reviews + approves + merges** any PR (`dev/PR_REVIEW.md`) — **don't self-merge**.
- Branch from latest `main` (`git pull` first); ship via PR. Standard tier → Gates 1, 2, 5.
