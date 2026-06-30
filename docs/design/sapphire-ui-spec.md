# Sapphire UI — design system & decisions

**Canonical visual spec:** [`design/full-ui.html`](../../design/full-ui.html) (self-contained mockup — open it).
Live-streaming-trace reference: [`design/trace-and-panel.html`](../../design/trace-and-panel.html).
Plan-first card reference: [`design/plan-canvas-mockup.html`](../../design/plan-canvas-mockup.html).

This doc is the durable record of the UI: the layout, the design system, every surface, the engine seams, and
the rationale — so future design/build choices have context. The build is **WO-8**
([`dev/work-orders/WO-8-web-ui.md`](../../dev/work-orders/WO-8-web-ui.md)), implemented into `web/` (Next 15 +
Tailwind v4 + the existing component set). When the mockup and this doc disagree, **the mockup wins** for visuals;
this doc wins for behavior/seams.

## The product, in one line
A daily tool for CNS drug-discovery diligence: ask a hard question → the firm convenes live (you watch the trace
populate) → you get a ranked, cited recommendation with the partner *spread* preserved → you interrogate any part
of it, pin what matters, and move on.

## Layout — three panes
```
┌ topbar: brand · A/B · ⌘K search · model · profile · panel-toggle ───────────────────────┐
│ rail (244, indigo)   │  chat (center, near-black)            │  work panel (indigo)       │
│  Workspace           │   user query                          │  [ Trace | Info ]   ⤢  ›   │
│   · Pinned           │   inline trace element (live→collapse)│   live-streaming trace     │
│   · Today / history  │   the rich result (synthesis…)        │   OR per-step Info+side-chat│
│  + New · search      │   composer (Plan first · send)        │   (chat bar in Info)       │
└──────────────────────┴───────────────────────────────────────┴────────────────────────────┘
```
- **rail** — Workspace: a **Pinned** section (pinned findings/steps) above the conversation **History**. New + ⌘K-search.
- **chat (center)** — the conversation: the user query, the **inline trace element**, and the **rich result**. This is
  the calm, readable hero; the firm's depth is one click away on the right.
- **work panel (right)** — the detail surface. Two tabs: **Trace** (the live firm process) and **Info** (full detail
  for one step, with a scoped **side-chat**). Expandable (`⤢` widen) and closeable. No "Dossier" tab — the cited
  facts live inside each step's Info, so a separate tab was redundant.

## Design system

### Tokens (see `:root` in the mockup; mirror into `web/src/app/globals.css`)
- **Surfaces:** chat `--bg:#08090a` (near-black, the focus); side panels `--side:#0d0c22` (faint indigo — the
  brand color the user picked); seam between chat and panels `--seam:rgba(124,99,196,.18)`; cards `--panel:#0e0f11`.
- **Brand / interactive accent = Quiver violet:** `--q:#8b5cf6` (+ `--q-bright #a78bfa`, `--q-text #c4b5fd`,
  `--q-d #7c3aed`, soft/bd/ring variants). Used for the wordmark gradient, active tabs, section labels, links,
  selected rows, primary buttons, the takeaway callout, the gem.
- **Semantic colors (do NOT recolor these — they carry meaning):** `--ok #3fb950` (real/done), `--danger #f85149`
  (veto/gate), `--warn #d29922` (divergence/caution), `--external #56b6ff` (external plane / blue),
  `--internal #c084fc` (internal plane / purple). Blue stays blue ONLY where it means external-plane data.
- **Type:** Geist sans (body + agent names), Geist mono (ids, provenance, metrics). `--r:.5rem` radii.
- **Glow:** restrained. The synthesis card has a *soft* violet bloom (`rgba(139,92,246,.11)` radial, low-spread
  shadow) — deliberately subtle, not the heavy glow of earlier drafts.

### Hard rule: NO EMOJIS / decorative glyphs
No `⚗ ◆ 🔒 🌐 ⛔ ⚑ ✦ ◌ ✓ ●` etc. — they read as AI-generated. Use:
- **Inline SVG icons** (lucide-grade): check, chevron(L/R), download, pin, panel, search, send, plus, expand, arrow.
  The mockup defines a minimal set in its `I` object; the build uses `lucide-react` (already a dep) for the same.
- **Colored status dots** for trace state: green check (done), red dot (veto gate), violet pulsing dot (running).
- Add a **lint/test that fails on emoji codepoints in `web/src/**/*.tsx`** so this can't regress.

## Surfaces & behavior

1. **Inline trace element** (chat) — while live: one calm line + spinner, plain-language phase ("Convening the
   roundtable…"). When done: collapses to a summary pill ("Convened the firm · 14 agents · 68 facts · 4 partners ·
   16s · show work"). Clicking it / "show work" focuses the Trace panel.
2. **Live Trace panel** — streams the REAL `run_live` execution (SSE; built in #144). Landmarks (Plan / Flags /
   Synthesis) + **collapsible buckets** (Bucket 1 fact agents, Bucket 2 roundtable). Each row: status dot + sans
   name + count + a **tight ~2-line summary** of that step's result. Rows reveal as the firm reaches them and stay
   clickable. Click a row → Info.
3. **Info tab** (per step) — the full detail: a violet **takeaway** callout, status/provenance/tier/timing/query,
   the **complete contributed-facts list** (each with source + tier), and — for partners — **round evolution**
   (R1→R2), full reasoning, dossier cites, and "how this fed the run". A **Pin** affordance.
4. **Scoped side-chat** — a chat bar at the bottom of Info + suggested questions + per-fact "ask". Asking opens a
   conversation **scoped to that step only** ("chatting about <step>"), answered from that step's facts + provenance
   alone. `‹ detail` returns.
5. **The rich result** (chat) — the synthesis: framing + **ranked candidates** (with reasoning + provenance) +
   **excluded** items + **confidence** rationale + **proposed experiment** + **known-unknowns (flagged, not faked)**
   + the **partner spread** (verdict cards; the spread is the product — never averaged) + a **provenance strip** +
   **follow-up** chips. Variant A keeps the panel open with a compact spread; variant B closes the panel and renders
   a wider report.
6. **Daily-use chrome** — **Pin/Workspace** (pin synthesis/steps to the rail; persists), **Export** (synthesis →
   cited Markdown), **⌘K command palette** (commands + jump-to-step + conversation search), **run notifications**
   (toast on convene + on complete, so a ~6-min live run doesn't trap you).

## Engine seams (documented, robust)
- **SSE trace stream** — `live_engine.run_live(on_progress=…)` already emits per-agent/partner events; the panel
  consumes them via a `ReadableStream` reader (built in #144). Keep.
- **Per-step summarizer** (NEW) — distills each agent's facts into one ~12–18-word takeaway. A small model call
  (haiku) with a **hard word budget** and **honesty guard** (only restate cited facts; flag uncertainty; never add
  a claim). Runs once per step as its facts land; **cached with the trace** so history replay is instant. This is
  "the skill that chooses the words carefully" — its prompt is where summary quality lives; spec it precisely.
- **Scoped side-chat** (NEW) — a context-scoped model call whose ONLY context is the selected step's facts +
  provenance, with a guard: "answer strictly from this evidence; if it's not here, say so." Cheap, daily-useful.
- **Honesty / data boundary (non-negotiable)** — provenance/tier/plane on every fact; internal moat scores never
  leave; unknowns flagged not faked. Carries through summaries, side-chat, and Export unchanged.

## Constraints (every phase)
- **RAM < 2 GB** — production serve (`next build && next start`, never `next dev`); SSE not polling; virtualize long
  lists (trace, facts); close streams on completion.
- **Tested** — a React component test harness lands in Phase 1; every surface ships component/smoke tests asserting
  it renders with zero console errors (this closes the gap that let a Rules-of-Hooks crash through in #144).
- **Robust to iteration** — token-driven styling (a restyle = token edits), componentized surfaces, the mockup +
  this doc as the source of truth. Future design choices change tokens/components, not the architecture.
