# Sapphire Full-Site Design Notes

_Design exploration — `design/` only. Do not ship without real-build review._

---

## Provider patterns → Sapphire translations

| Provider | Pattern studied | Sapphire adoption |
|---|---|---|
| **Claude.ai** | Plan mode: substantive prose steps, not bullet chips. Extended-thinking collapse. Calm, centered empty state with gem logo. | Plan card uses full narrative framing + specific per-step expectations (same grammar as approved `plan-canvas-mockup.html`). Empty state leads with the gem, sub-headline, and honesty strip — not a feature list. |
| **Perplexity** | Sources-forward: citations inline with facts. Two-column layout for internal vs. external sources. "Steps" search-process disclosure. | Dossier splits into two planes (internal moat vs. public literature) each with provenance chips on every card. The live-run surface shows each agent as a "step" lighting up, borrowing Perplexity's process transparency without its dense text wall. |
| **ChatGPT / o1** | Reasoning collapse: "Thought for Ns" summary visible but collapsible. Minimalist model picker in topbar. | The live-run surface shows agent status rows with spinner/done dots — the firm's "reasoning" is visible as it runs, not hidden. Topbar carries model + profile pills (minimal, like ChatGPT's model picker). |
| **Linear / Vercel v0** | Dark Geist aesthetic: `#08090a` background, hairline borders `rgba(255,255,255,.07)`, tight radii, accent used sparingly. Dense but not crowded. | Token-exact match from `globals.css`. Borders, radii, type sizes, scrollbars all copied verbatim. The inspector right rail echoes Linear's side panel pattern (tabbed, closeable). |
| **Raycast / Cursor** | ⌘K command palette: instant navigation + action dispatch from anywhere. Inspector/side panel that opens on selection. | Full ⌘K palette implemented (keyboard shortcut wired). Inspector opens on any fact or verdict card click, showing agent metadata + live trace — exactly like Cursor's contextual info panel. |

---

## Surface-by-surface recommendations

### 1 — Landing / empty state
**Decision:** gem logo → h1 "Sapphire" → 1-sentence value prop → 4 example CNS queries → honesty strip. No feature lists, no animation, no hero imagery.

**Tension trade-off:** The firm is powerful (20 agents, multi-round deliberation) but the first view must be calm. Resolved by restraint: the honesty strip shows the badge vocabulary (`● moat-real`, `T2`, `⛔ VETO`) without explaining each — it signals depth without dumping it. Power is available on the first keypress.

**Borrow from:** Claude.ai home (centered, gem, one composer). Perplexity focus modes (the example query categories act as implicit focus shortcuts).

---

### 2 — Plan-first
**Decision:** Reuse the approved plan-card grammar verbatim (gradient-to-b + radial glow + uppercase accent header). Narrative prose per step — not chip summaries. The `expect:` inline box makes the plan falsifiable ("I expect PMID 12172553") rather than vague.

**Tension trade-off:** Substantive prose vs. quick scannability. Resolved with the numbered step spine + the `expect:` / `skipping:` semantic boxes — a scientist can scan the step headings in 5 seconds or read the full rationale in 30.

**Borrow from:** Claude Code plan mode (prose steps with specific expectations). The `⛔ veto` step styling (red num box) distinguishes gate steps visually without extra copy.

---

### 3 — Live run / firm convening
**Decision:** Agent status rows with three states (waiting gray → running blue pulse → done green). Internal/external plane badges on each row. Fact count as the row's outcome signal. Bucket 2 shown queued but visible — the user can see the full firm before it runs.

**Tension trade-off:** Showing 13+ agents without creating a wall. Resolved by the `agent-row` component: one line per agent, status dot + name + sub-description + 2–3 chips + fact count. Everything fits in ~36px. The roundtable section renders as lighter "waiting" rows to signal it's next without competing with the active bucket.

**Borrow from:** Perplexity's search step disclosure (process visibility). GitHub Actions job matrix (status grid, not a log wall).

---

### 4 — Cited fact dossier
**Decision:** Two-column layout — `🔒 internal` (purple plane) left, `🌐 external` (blue plane) right. Every fact card carries honesty badges inline: tier chip + provenance chip + plane chip + flag chip if flagged. Mock/stub facts get dashed borders and italic text — visually demoted, never hidden.

**Tension trade-off:** 21 facts is too many to show flat, but collapsing too aggressively hides the evidence. Resolved with progressive disclosure: top 5–6 cards shown per plane, with an "expand all" ghost entry. Click any card → Inspector opens with full agent/provenance metadata. The DIVERGENCE flag gets a full callout, not just a chip — it's a signal, not noise.

**Borrow from:** Perplexity sources panel (citation inline, source label prominent). The internal/external split is Sapphire-specific — no equivalent in any AI product today. That distinction IS the value.

---

### 5 — Roundtable / spread
**Decision:** 2×2 verdict card grid. Each card has a 3px left-side stance bar (green/yellow/red), partner name, ADVANCE/CAUTION/BLOCK label, full rationale prose (3-line clamp, expand on inspect), conviction bar (5-dot), and provenance chip. Round 1 / Round 2 toggle preserved — the evolution of each partner's view is part of the product.

**Tension trade-off:** This is the most novel surface — the spread must NOT be flattened to a score or a consensus summary. But 4 dense cards can feel like a wall of text. Resolved by the conviction bar (visual density without prose), the stance bar (scannability at a glance), and the rebuttal note below (the moderator's summary of what changed between rounds — explains the narrative arc without hiding the disagreement). The summary bar at the bottom ("2 ADVANCE · 2 CAUTION · 0 BLOCK") gives the gestalt without pretending there's a winner.

**Borrow from:** Nothing directly — this is the novel surface. Closest reference: a VC investment memo where each partner's view is presented separately before a decision. The key design rule is: no consensus meter, no single score, no "Sapphire thinks X" — the spread IS the product.

---

### 6 — Synthesis
**Decision:** Same synthesis-card grammar (blue gradient + radial glow + uppercase accent header with ◆ icon). Three sections: recommendation prose → proposed experiment box → known-unknowns box. Confidence shown inline with tone color (low/med = warn yellow, high = ok green). Compact spread recap below the card.

**Tension trade-off:** The synthesis must be decisive enough to act on but honest about uncertainty. Resolved with the known-unknowns box as a first-class section — not a footnote. "Flagged, not faked" is enforced structurally: if we don't know, there's a box for it. The proposed experiment converts the uncertainty into an action, which reframes "we don't know" as "here's how to find out."

**Borrow from:** Claude artifacts (the card-as-deliverable grammar — a distinct styled block, not chat prose). The proposed experiment borrows from scientific reports that pair a finding with a next experiment.

---

### 7 — Inspector (right rail)
**Decision:** Two-tab panel (Investigate + Monitor). Investigate shows the selected fact or verdict's full metadata (agent_id, provenance, tier, source, flag, duration). Monitor shows the append-only trace log with timestamps. Opens on click of any fact or verdict card; ⌘I shortcut. Closeable with ✕.

**Tension trade-off:** Power users want the trace; most users just want to click a fact. Resolved by making the panel optional (closed by default, opens on click) and defaulting to Investigate (the actionable tab) rather than Monitor (the technical log).

**Borrow from:** Cursor's info panel (opens contextually on selection). Linear's side panel (tabbed, closeable, doesn't take screen space until needed).

---

### 8 — History rail + ⌘K palette
**Decision:** History rail shows conversation title, subtitle (stage or outcome), and age. Section dividers (Today / Yesterday). ⌘K palette overlays with surface navigation + action dispatch. Palette filters on keystroke.

**Tension trade-off:** The history rail is secondary UX — most sessions are focused on one run. Kept at 248px (same as `plan-canvas-mockup.html`) with no collapse mechanism in the mockup, but the real build should add a collapse toggle for focused-mode users.

**Borrow from:** Raycast command palette (instant navigation, keyboard-first). ChatGPT conversation history rail (title + subtitle + age format).

---

### 9 — Composer
**Decision:** The composer is consistent across all surfaces. Plan-first toggle (sm switch + label) is always visible. Honesty tagline ("Sapphire never fabricates — unknowns are flagged, not faked") is always right-aligned. Placeholder text adapts per surface (idle vs. plan-adjust vs. mid-run vs. dossier-drill). Status line replaces the honesty tag during a live run.

**Tension trade-off:** The composer needs to be functional at every stage but not steal attention from the results. Resolved by keeping it structurally identical across surfaces — the user always knows where it is and what it does.

---

## Prioritized build order (for real `web/` implementation)

1. **Synthesis card** — already exists in `web/src/components/run/synthesis.tsx`; highest value, easiest port. Verify the gradient + glow renders correctly.
2. **Spread / roundtable** — `run/spread.tsx` exists; add the round-1/round-2 toggle and the conviction bar. The rebuttal-note component is missing — add it.
3. **Dossier two-plane layout** — `run/dossier.tsx` has the column structure; ensure the plane header (icon + label + count) renders and the mock-card dashed-border styling is wired.
4. **Live-run agent grid** — new component. The streaming SSE trace from `frontend2/` already emits per-agent events; wire them to this grid.
5. **Inspector tabs** — `inspector/` exists; the Investigate tab needs the full fact metadata view (not just the agent list). Monitor tab already has the trace.
6. **Plan card** — already in `plan-review.tsx` (currently a flat checklist); promote to the prose-step grammar from `plan-canvas-mockup.html`. This is the most important narrative surface.
7. **Landing / empty state** — `empty-state.tsx` exists; add the honesty strip and example query buttons.
8. **⌘K palette** — `command-palette.tsx` exists; wire surface navigation actions.
9. **Composer status line** — adapt `composer.tsx` to show live-run progress in the meta row.
