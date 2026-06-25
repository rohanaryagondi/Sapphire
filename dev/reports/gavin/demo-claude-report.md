# Report — Demo Claude: working live Sapphire demo on the redesigned front-end

**Owner:** gavin · **Task:** `demo-claude` · **Date:** 2026-06-25
**Brief:** `docs/superpowers/plans/2026-06-25-gavin-demo-claude.md`
**Role note:** Demo Claude does **NOT** gate/merge — Head Claude (Rohan) is the approver. This report
flags findings; it does not change runtime code.

## TL;DR

The demo **works end-to-end** on the redesigned front-end. A TSC2 run renders the full firm —
real moat + real EMET PMIDs + the roundtable spread + synthesis — honestly labeled. Standing it up
needed no code change (all merged via #93/#94). Verified by driving the browser with Playwright.

## What I ran

```bash
git checkout main && git pull origin main          # synced to 9fae296 (+ #94 restyle)
pip install -r frontend/requirements.txt           # chainlit==2.9.5, pandas
cd frontend && chainlit run main.py --port 8002    # free port (8000/8001 left for other sessions)
```

Drove the browser via Playwright (the EMET agent's tool): selected a profile, asked
*"Is TSC2 a viable target in tuberous sclerosis?"*, and verified every section rendered.

## Profile / data used

I do **not** have Rohan's gitignored `RohanOnly/` data on this machine (no `moat.sqlite`,
no `boltz_api.env`, no EMET creds) — so the real-time **Live** profiles would degrade their moat/EMET
to empty (honestly). As the brief anticipates, I used the **committed frozen-real** path:

- **`Replay (TSC2 · session-bridge EMET · $0)`** — the flagship I demoed. A frozen REAL `run_live`:
  real Quiver moat + **9 real EMET PMIDs** (captured live in the authenticated BenchSci session,
  injected via the session-bridge) + the real haiku persona spread. Instant, deterministic, $0.
- Also verified headless: `Replay (captured TSC2 · $0)` and `Demo (mock backends)` (the engine runs
  its real logic over the offline ctx in ~1.3s).

## What rendered (verified in the live DOM)

- **Restyle is live** — my chat-first design is the runtime look (#94): dark ground, sapphire-blue
  `#4d7cfe` rounded send button, rounded input, "Sapphire" wordmark, the user's question in a
  right-aligned rounded bubble. Matches `docs/design/console-ui/sapphire_chat.html`.
- **Plan** — deliverable / disease (tuberous sclerosis / mTORopathy CNS) / modality; Bucket-1 agents
  incl. **FDA Institutional Memory ⛔** (veto marker shown); the 5-partner roundtable panel.
- **Firm roster** — Bucket-1 fact-agent table (internal-science-lead, emet-analyst, q-models-runner,
  fda-institutional-memory, patent-ip, global-regulatory-divergence, …) with status + provenance.
- **Two data planes, distinct** — Internal Vault (`moat-real`, 8 facts incl. TSC1~TSC2 KO cos 0.083)
  vs External Evidence (`emet-live`, 9 real PMIDs: 36806388, 35963265, 35169091, 34399110, 29478616,
  26060906, 23622183, 21329690, 11112665). Every fact carries **tier + provenance** verbatim.
- **⛔ VETO** and **⚠ DIVERGENCE** sections render with their honest headings (surfaced, not
  reconciled).
- **Roundtable spread (no forced consensus)** — Denali, BioMarin (conditional), Third Rock
  (conditional), Takeda (conditional) each citing the dossier; **Adversarial Red-Team abstained
  (guardrail-violation)** — shown honestly with its reason, not dropped.
- **Synthesis** — *Conditional advance — 3 conditional verdicts · medium confidence*; proposed
  experiment; entities (TSC2); engagement trace `eng_6444d0e8`.

Screenshots captured on `C:\Users\gavin.wong\Desktop\` (demo-landing, demo-tsc2-top/mid, demo-tsc2-full).

## Gaps / things to flag to Head Claude (not fixed — not my call)

1. **No `RohanOnly/` data here** → the true real-time Live profiles (live moat/EMET/Boltz) can't run on
   my machine. The frozen-real Replay path covers the demo fully and honestly. For a true live drive,
   run on Rohan's device or have the `RohanOnly/` data shared.
2. **Real model reasoning is still 🧪 simulated** (roundtable + claude fact-agents) — a pending product
   decision per the runbook, not something to flip for the demo.
3. **Minor cosmetic:** switching the chat profile *mid-session* leaves the previous welcome message
   visible (two welcomes). A **fresh page load shows exactly one** — so for the demo, pick the profile
   on load (or reload after switching). Low priority; flagging in case a one-line `on_chat_start`
   clear is wanted.
4. **Benign console noise:** a 400 on `/avatars/Sapphire%20—%20CNS%20Decision%20Firm` (em-dashes in the
   assistant display name) and `*/*` MIME warnings from Chainlit's bundle. Cosmetic; no demo impact.

## Recommended demo flow for tomorrow

1. `cd frontend && chainlit run main.py --port 8002` → open `http://localhost:8002`.
2. On the fresh page, pick **`Replay (TSC2 · session-bridge EMET · $0)`** (guaranteed-visible, $0).
3. Ask *"Is TSC2 a viable target in tuberous sclerosis?"*.
4. Walk the story (per `frontend/DEMO_TSC2.md`): plan → two planes (moat vs 9 real PMIDs) → VETO →
   DIVERGENCE → the spread (3 conditional + Red-Team abstain) → synthesis. Label it replay (frozen real),
   not a fresh live drive.
