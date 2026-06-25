# Sapphire Console — UI/UX design

> **⚠ INTERNAL ONLY.** These mockups embed **real internal TSC2 moat values** (the `moat-real`
> signatures, consistent with the committed `sapphire-orchestrator/scenarios/tsc2_live_run.json`
> scenario). They are design artifacts for the team — do **not** publish, screenshot for external
> decks, or share outside Quiver. The data boundary that governs the product also governs these files.

This directory holds the **design exploration for the Sapphire Console** — the front face of the
two-bucket firm. It is **design iteration only**: it does **not** change the runtime app in
`frontend/`. The chosen direction (`sapphire_loka.html`) is meant to fold into `frontend/` later,
once the design is signed off.

## The 3-pane vision

The console renders the *whole firm process* in one screen — facts on the left, the firm's answer in
the middle, the proof on the right:

| Pane | What it shows | Why |
|---|---|---|
| **LEFT — agent output cards** | Each fact agent's output, **grouped by the two data planes**: an **Internal Vault** group (the Quiver moat — EP/CRISPR signatures, `moat-real`) and an **External Evidence** group (EMET PMIDs, Q-Models, semantic web agents). Every card carries its **tier + provenance**. | The dossier *is* the firm's evidence. Splitting it by plane makes the data boundary visible and keeps "what's ours" vs "what's public" unmistakable. |
| **CENTER — response** | The synthesis verdict (e.g. *Conditional advance*), the **roundtable spread** (each partner's independent verdict + the moderated rebuttal — **no forced consensus**, the spread is the product), and **DIVERGENCE** callouts (internal↔external conflicts, surfaced, never auto-reconciled). | This is the deliverable: the facts **plus** how each player reacted. The spread and the divergences are the alpha. |
| **RIGHT — live trace** | The harness trace, step by step (plan → each Bucket-1 agent with result + timing, internal moat + EMET visibly first → flags → each persona verdict → synthesis). | Transparency. Every box is auditable; abstentions and tool-failures show honestly rather than vanishing. |

## Why the ★ LOKA-native console is the chosen direction

`sapphire_loka.html` (★) is the design we carry forward. It is **not a new aesthetic** — it is the
**same running app, reorganized**:

- It reuses **Chainlit's exact shadcn token system** (`--background`, `--card`, `--border`,
  `--muted-foreground`, `--radius`, …) lifted from the app's `theme.json`.
- The **only brand override is Quiver purple** as `--primary` (`hsl(300 85% 55%)`) — the same
  `--primary` the runtime `frontend/` already sets.
- It uses the **Sapphire / Quiver gem mark** (inline SVG, recolored to `--primary`) and the
  **Inter** typeface — so it reads as the *same product*, just laid out as a 3-pane console instead of
  a single chat column.

The bet: when this folds into `frontend/`, it should feel like the running app grew two side rails,
not like a re-skin. Staying on the LOKA/Chainlit token system is what makes that possible.

## The three earlier explorations (kept for range)

Off the LOKA skin — kept so we can borrow ideas, **not** as candidates to ship as-is:

- **A · Mission Control** (`variant_a.html`) — dense, telemetry-forward dark layout; a "control room"
  read of the firm.
- **C · The Firm** (`variant_c.html`) — a more editorial dark layout that leans into the
  "firm / partners" framing.
- **B · Exec Brief** (`variant_b.html`) — **light-themed**, a polished one-page brief read (serif
  display type). The outlier on theme; useful for thinking about an exec-facing export.

The **switcher** (`index.html`) flips between all four.

## Open design choices — for Gavin to refine

These are genuinely open; iterate them **with Gavin**, staying inside the LOKA/Chainlit tokens:

1. **Trace rail (right):** **Step-tree** (collapsible plan → agents → personas → synthesis) vs
   **Live-stream** (a running log of events). The mockup shows a segmented toggle for both — which is
   the default, and do we keep both?
2. **Density:** comfortable vs compact (a toggle is mocked) — what's the default, and how compact can
   the left cards get before tier/provenance becomes illegible?
3. **Left-card grouping:** how the two-plane grouping reads — group headers? a vertical divider? color
   weight? How do we signpost *which plane* a card belongs to at a glance.
4. **The spread + DIVERGENCE:** how the roundtable spread reads in the center (chips? a small matrix?
   per-partner cards?) and how a `DIVERGENCE` finding is visually distinct from an ordinary fact.
5. **Signposting the two data planes:** the strongest, simplest visual language for "Internal Vault"
   vs "External Evidence" — without ever implying the two are interchangeable.

## Honesty requirements — must survive any refinement

These are **non-negotiable** and constrain every design decision (they mirror the product's hard
rules):

- **Tier + provenance on every fact.** No fact renders without both.
- **The two data planes stay visually distinct.** Internal (vault) and external (public) must never be
  visually merged or made to look interchangeable.
- **`● live` vs `🧪 simulated` is never conflated.** Live data, simulated-model output, and stubs each
  carry a distinct, unmistakable marker wherever they render. (Per the current demo: real EMET + real
  moat + real seams are live; model reasoning may be labeled-simulated — it must *say so*.)
- **Abstentions and tool-failures show honestly.** An agent that abstains or fails is rendered as such
  (with its reason), never silently dropped.
- **Veto facts read as gates**, not silent kills; **DIVERGENCE** reads as surfaced, not reconciled.

## How to view

```sh
python3 -m http.server 8090 --directory docs/design/console-ui
# then open http://localhost:8090/index.html  (the switcher; ★ LOKA-native loads first)
```

Every file is **self-contained and binary-free**: the brand mark is an inline SVG (the Quiver gem,
recolored to `--primary`); the favicon is an inline `data:` URI. The only network reference is the
Google Fonts CDN for **Inter** (the app's typeface), which degrades gracefully to `system-ui`. No
images or other assets are committed here (Gate-3 blocks committed binaries; the real `logo_dark.png`
already lives at `frontend/public/`).
