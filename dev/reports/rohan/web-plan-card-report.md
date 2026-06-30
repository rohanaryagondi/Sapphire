# WO-7 Phase B — PR report (the prose plan-mode card + real narration)

**Branch:** `rohan/web-plan-card` · **Built-By:** rohan · **Tier:** Feature (engine + bridge + web/)
**Spec:** `dev/work-orders/WO-7-web-live-firm.md` (Phase B) + mockup `design/plan-canvas-mockup.html`
**Workboard:** `web-live-firm-BCD` (🔨 HIGH, Phase B first). **For:** Head Claude to gate + merge (I don't self-merge).

## Goal
With **Plan-first** ON, the firm proposes a **prose plan** (no agents run) → user approves → the live run streams
(Phase A). Refactor `web/src/components/plan-review.tsx` from the flat agent checklist to the narrative plan card,
backed by a **real LLM narration with a deterministic fallback**.

## Key framing (this was NOT frontend-only)
The DoD's "narration is **real (LLM)** with a working fallback" required adding a narrated plan to the engine's
plan-mode envelope — the prior envelope only carried terse fields (`deliverable/disease/modality/agents/panel`).
So Phase B spans **engine + bridge + web/**, over 5 stable canonical steps (moat → external → veto → roundtable
→ synth).

## What shipped (commits 265054f → ac7caff → d555e1c)
**Backend (stdlib engine; LLM via the existing `claude -p` planner — no second call):**
- `sapphire-orchestrator/smart_plan.py` — `_SMART_PLAN_SCHEMA` + planner prompt extended so the planner ALSO
  returns a `narrative` (`framing` + 5 canonical `steps`) **in the same call**; public identifiers only.
- `sapphire-orchestrator/plan_narrative.py` (NEW) — `build_deterministic_narrative()` (stdlib templated fallback,
  stamps `source="deterministic"`) + `FORBIDDEN_NARRATIVE_TERMS` + `_scrub_narrative_text()` (data-boundary).
- `sapphire-orchestrator/live_engine.py` — the `llm+approve` path uses the LLM narrative when valid AND it passes
  the data-boundary scrub → stamps `narrative.source="llm"`; otherwise falls back to the deterministic builder
  (`source="deterministic"`). The scrub means a leaked internal-score term in LLM prose can never reach the user.
- `frontend/bridge.py` — `narrative` passes through verbatim; the error path also builds a deterministic narrative
  (the card never receives `undefined`).

**Types:** `web/src/lib/types.ts` — `PlanStep` + `PlanNarrative` (incl. `source: "llm" | "deterministic"`),
`PlanEnvelope.narrative` optional.

**Frontend:** `web/src/components/plan-review.tsx` — rebuilt to the prose card (synthesis-card grammar: accent
eyebrow + gradient + glow): framing paragraph, 5 numbered timeline steps (prose + `expect:`/`skipping:` callouts +
plane/provenance/veto **badges from `ui/chips.tsx`**), an "edit the agents" disclosure that demotes the old
checklist with **locked veto pills** (`fda-institutional-memory ⛔`, `patent-ip ⛔`), and **Approve & Run** via the
existing `approvePlan` (pendingPlan.agents[].selected stays the source of truth). The "templated plan" honesty
label is keyed to **`narrative.source !== "llm"`** (the prose author), NOT `plan_source` (agent selection).

## Gate evidence
- **Gate 1 — full suite GREEN: 876 tests** (`bash dev/run-tests.sh`, local moat DB present) — incl. the new
  `test_plan_narrative.py` (deterministic structure/plane/veto/roundtable, `source` stamping, the live_engine
  fallback plumbing, and the data-boundary scrub end-to-end). `npm run build` 0 type errors.
- **Gate 2 — independent review: Approved-with-nits** — confirmed the load-bearing honesty invariant
  (`narrative.source` drives the label, no path reads `plan_source` for it), engine stdlib-only, non-vacuous
  tests. Its two findings were fixed (see Fix-loop).
- **Gate 5 — independent functional verification: PASS** (clean isolated env, fresh ports + `SAPPHIRE_API`).
  Built prod, drove plan-mode via Playwright: prose card renders (framing + 5 steps + badges + locked veto pills),
  the **"templated plan" label shows** for the deterministic path, **Approve & Run transitions to a live
  streaming run**; backend envelope carries `narrative` + `source`; data-boundary grep clean; **peak RAM
  ~0.14 GB** (≪ 2 GB); tests non-vacuous.

## Honesty notes (read these)
- **I caught + fix-looped a DoD gap the implementer first reported as "no deviation."** The first pass never made
  the LLM produce the narration (the planner schema had no `narrative` field), so it was ALWAYS the deterministic
  builder — while a `plan_source="llm"` plan rendered with NO "templated" label. Fixed: (1) the planner now emits
  the narrative (real LLM), (2) the card labels off the **narrative's own source**, so templated prose is always
  labeled even when the LLM selected the agents.
- **Data boundary is enforced mechanically, not just requested.** Beyond the prompt's "public identifiers only,"
  `_scrub_narrative_text` drops any LLM narrative containing internal-score terms (cosine/ep_score/cnsdp/dfp_score/
  reversal_strength) → deterministic fallback. The deterministic builder is test-guarded against the same terms.
- **Real-LLM narration end-to-end is Head's authoritative gate.** Gate 5 verified the schema/plumbing + the
  deterministic path live; a real-haiku plan-mode run (to observe `source="llm"` with the label hidden) needs live
  Claude infra — please confirm in your gate.
- **depth/roundtable controls omitted** (honest): only `approved_plan: string[]` crosses the wire, so showing
  controls that silently do nothing would mislead. Noted for a future phase if a channel is added.

## Operational note (for running/gating)
Next.js bakes the `/api` rewrite target at **build time**, so to point the web app at a non-default backend port
you must set the env var on the BUILD: `SAPPHIRE_API=http://127.0.0.1:<port> npm run build` (then `next start`).
The default (`:8201`) works for the standard `frontend2/server.py` deployment.

## Files changed
`sapphire-orchestrator/{smart_plan,live_engine,plan_narrative}.py` + `sapphire-orchestrator/tests/test_plan_narrative.py`;
`frontend/bridge.py`; `web/src/lib/types.ts`; `web/src/components/plan-review.tsx`. Engine stays stdlib-only; no
Phase C/D files touched (run/spread.tsx, run/synthesis.tsx, command-palette.tsx untouched).

## DoD checklist
- [x] Plan-first shows the prose plan card (framing + 5 steps + badges + locked veto + agent-pills disclosure)
- [x] Approve → live run streams (Phase A behavior)
- [x] Narration is real (LLM) with a working, honestly-labeled deterministic fallback (+ data-boundary scrub)
- [x] Full suite green (876); peak RAM ~0.14 GB ≪ 2 GB; engine stdlib-only; data boundary intact
- [x] Gate 2 Approved (nits fixed) · Gate 5 PASS (clean env, Playwright)
- [ ] Authoritative real-Haiku plan-mode run (observe `source="llm"`) — **Head Claude's gate**

Next: Phase C (`rohan/web-spread-synth`) then Phase D (`rohan/web-dossier-cmdk`), each its own gated PR.
