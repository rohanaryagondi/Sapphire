# WO-8 — web/ : the Sapphire UI (the daily tool)

**Owner:** Rohan Claude · **Approver:** Head Claude · **Target:** `web/` (Next 15 + Tailwind v4 + the existing
component set). **Authored:** 2026-06-30, after a long design iteration with the user (every screen reviewed).

**Build the approved mockup into `web/`.** Canonical visual spec: **[`design/full-ui.html`](../../design/full-ui.html)**
(open it — it's self-contained and interactive). Design system + decisions + engine seams:
**[`docs/design/sapphire-ui-spec.md`](../design/sapphire-ui-spec.md)**. When the mockup and the spec disagree, the
mockup wins for visuals, the spec wins for behavior/seams.

## Locked decisions (do not re-litigate)
- **3-pane app:** rail (Workspace = Pinned + History) · chat (the conversation + the rich result) · work panel
  (Trace | Info, expandable). No Dossier tab.
- **Live-by-default + Haiku** (from WO-7); the trace **streams the real `run_live`** (#144 is merged — build on it).
- **Design system:** chat near-black `#08090a`; **side panels faint indigo `#0d0c22`** with a faint-purple seam;
  **Quiver violet `#8b5cf6`** as the brand/interactive accent; semantic colors kept (green=real, blue=external,
  purple=internal, red=veto, amber=divergence); Geist; restrained glow.
- **NO EMOJIS** anywhere — inline SVG icons (`lucide-react`) + colored status dots only. This is enforced by a test.
- **Honesty + data boundary** intact throughout (provenance/tier/plane; internal scores never leave; unknowns
  flagged not faked). **RAM < 2 GB** (production serve, SSE not polling, virtualized lists).

## Robustness requirements (the user will iterate the design later — make that cheap)
- **Token-driven styling** — all colors/radii/spacing from `globals.css` tokens; a restyle must be a token edit, not
  a component rewrite. Mirror the mockup's `:root` exactly.
- **Componentized surfaces** — each surface is its own component; no monoliths.
- **A React component test harness lands in Phase 1** and every later phase ships component/smoke tests (this closes
  the gap that let a `tsc`-invisible Rules-of-Hooks crash through in #144). A run is not "done" without its tests.
- **An emoji-lint test** fails CI if any emoji codepoint appears in `web/src/**/*.tsx`.

## Phases — one gated PR each (sequential; Head Claude gates + merges)

### Phase 1 — design system + app shell · branch `rohan/web-ui-shell`  (ASSIGN NOW)
The foundation everything else builds on.
- **Tokens:** update `web/src/app/globals.css` to the mockup's palette — `--bg`, `--side` (indigo `#0d0c22`),
  `--seam`, the Quiver-violet `--q*` family as the brand accent, semantic colors, softened glow values.
- **Icon set:** standardize on `lucide-react`; **remove every emoji/decorative glyph** already in `web/` and replace
  with SVG icons + colored status dots. Add the **emoji-lint test**.
- **Shell:** the 3-pane layout (rail / chat / work) with the indigo sides + faint-purple seams; **topbar** (violet
  wordmark, A/B variant toggle, ⌘K search pill, model + profile pills, panel toggle); **composer** (Plan-first,
  send). Rail shows Workspace header + (empty) Pinned slot + History + New + search. Wire the existing store; no new
  data behavior yet — this is the chrome + tokens.
- **Test harness:** add a React component test runner (Vitest + React Testing Library, or Playwright-ct) wired into
  `dev/run-tests.sh`; ship a smoke test that mounts the shell and asserts zero console errors.
- **DoD:** shell + topbar + composer render per the mockup; tokens applied (indigo sides, violet accent, soft glow);
  **zero emojis** (lint test green); component harness runs in the suite; full suite green; **production build, peak
  RAM < 2 GB** (report it). Head Claude gates (Gate-5 = a real `next build && next start` render + RAM).

### Phase 2 — live trace panel · branch `rohan/web-ui-trace`
- Refit the right **Trace** tab to the mockup: landmarks (Plan/Flags/Synthesis) + **collapsible buckets**;
  **decluttered rows** (status dot + Geist-sans name + count + a **2-line per-step summary**); rows reveal as the
  firm streams (build on #144's SSE) and stay clickable; remove the Dossier tab.
- **Per-step summarizer (engine seam):** add a documented backend step that distills each agent's facts into one
  ~12–18-word takeaway — small model (haiku), **hard word budget**, **honesty guard** (only restate cited facts;
  flag uncertainty; no new claims). Run once per step as facts land; **cache with the trace** (instant on replay).
- **DoD:** trace streams live with summaries appearing per step; buckets collapse/expand; rows clean (no emojis,
  body font); summarizer real + unit-tested (word-budget + honesty asserts); component tests; suite green; RAM < 2 GB.

### Phase 3 — Info tab + scoped side-chat · branch `rohan/web-ui-info`
- The detailed **Info** view (takeaway callout · status/provenance/tier/timing/query · full contributed-facts list ·
  for partners: round-evolution + full reasoning + dossier cites + how-it-fed). Click a trace row → Info; **Pin** on
  the step.
- The **scoped side-chat:** a chat bar + suggested questions in Info, and a per-fact "ask". Asking opens a
  conversation **scoped to that step only** (context = that step's facts + provenance, with a "don't exceed this
  evidence" guard). `‹ detail` returns.
- **DoD:** Info matches the mockup; side-chat is scoped + honest (a test proves it won't answer beyond the step's
  evidence); component tests; suite green.

### Phase 4 — the rich result + Export · branch `rohan/web-ui-result`
- The synthesis in the chat: framing + **ranked candidates** (reasoning + provenance) + **excluded** + **confidence**
  rationale + **proposed experiment** + **known-unknowns (flagged, not faked)** + the **partner spread** (verdict
  cards; never averaged) + **provenance strip** + **follow-up** chips. Rendered from the real `run_live` contract
  (extend `run/synthesis.tsx` + `run/spread.tsx`). Variant A (panel open, compact spread) / B (panel closed, wider
  report).
- **Export:** synthesis → cited Markdown (clipboard + download).
- **DoD:** rich result renders from a real run; spread preserved; Export produces a faithful cited brief; component
  tests; suite green.

### Phase 5 — daily-use chrome · branch `rohan/web-ui-chrome`
- **Pin / Workspace:** pin the synthesis or any step → a **Pinned** section in the rail; **persists** (the stdlib
  SQLite store). **⌘K command palette:** commands (New query · Export · Pin · Switch model · Replay) + jump-to-step
  + conversation search, keyboard-driven (Cmd/Ctrl-K, Esc). **Run notifications:** toast on convene + on complete;
  survives navigating away (a live run is ~6 min).
- **DoD:** pins persist across reload; ⌘K navigates + dispatches; notifications fire on real run start/finish;
  component tests; suite green.

## Lifecycle
`/sapphire-build` per phase; blocked → `dev/HELP.md`. One branch per phase (`rohan/web-ui-*`), one gated PR each;
**Head Claude gates + merges** (Gate 1 suite green · Gate 2 independent review · Gate 5 functional verify — for the
UI phases the Gate-5 is a real `next build && next start` render + a RAM measurement + zero console errors). Build
from the **latest** `origin/main` (`git fetch origin` first — Gate 3.6 warns on a stale base).
