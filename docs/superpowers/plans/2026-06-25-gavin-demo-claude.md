# Task brief — Gavin: run a "Demo Claude" to stand up the working live demo

*Owner: **gavin**. Tier: **Standard**. Created 2026-06-25 by Head Claude.*

## Goal
Stand up a **working live Sapphire demo** — on **your** redesigned front-end (now the runtime look,
merged via #94) — and run it for viewing. You do this by running a **"Demo Claude"** session (a Claude
in this repo) that does everything needed to get the demo working and drives it. You're the UI lead and
the design author, so you own getting it to *look right while it runs*.

You are **NOT** the approver — **Head Claude (Rohan's session) remains the approver/gater**. Your Demo
Claude does **not** gate, merge, or push PRs; if you hit a bug or want a runtime change, flag it to Rohan
/ Head Claude (or `dev/HELP.md`), don't fix-and-merge yourself.

## Read first
1. `docs/reports/LIVE-DEMO-RUNBOOK.md` — the full state + demo runbook (what's REAL vs 🧪 SIMULATED vs
   CAPTURED, the profiles, EMET architecture, Boltz, the honest gaps). **Read it all.**
2. `CLAUDE.md` + `sapphire-orchestrator/AGENTS.md`.
3. Your design is already the runtime look: `frontend/` was restyled to your chat-first design in #94
   (`frontend/public/theme.json` + `custom.css` + `custom.js`; sapphire-blue accent `#4d7cfe`, Inter,
   "Ask Sapphire" hero, rounded bubbles, mono chips, CoT step-tree styling). Source mockups:
   `docs/design/console-ui/sapphire_chat.html`.

## The Demo Claude prompt (paste into your Demo Claude session)
```
You are "Demo Claude" for Sapphire. Your ONE job: stand up and run a working live Sapphire demo for the
viewer, on Gavin's redesigned front-end, with full visibility. You are NOT the approver — Head Claude
(Rohan's) owns all PR gating/merging; you do not gate/merge/push. Drive the demo's browser via computer
use (or Playwright if computer use isn't available); Playwright is also what the EMET agent uses.

Read first: CLAUDE.md, docs/reports/LIVE-DEMO-RUNBOOK.md (fully), docs/design/console-ui/sapphire_chat.html.

Run it:
  git pull            # get #94 (your restyle) + latest
  cd frontend && chainlit run main.py --port 8002    # USE A FREE PORT (8000/8001 may be other sessions)
  open http://localhost:8002

Demo flow (runbook §3–§4):
1) Pick the profile that works for your data (see "Data" below): "Live (demo · simulated models)" if you
   have RohanOnly/ data; otherwise "Replay (TSC2 · session-bridge EMET · $0)" (a frozen REAL run) or
   "Demo (mock backends)".
2) Ask "Is TSC2 a viable target in tuberous sclerosis?" → watch the step-tree stream: plan → moat (8) →
   EMET (real PMIDs) → seams → semantic (🧪) → flags → roundtable (🧪 spread) → synthesis
   ("Conditional advance · medium").
3) Boltz (real hosted API, ~min fold; only if RohanOnly/boltz_api.env present): FKBP12 (UniProt P62942,
   108 aa) + Isorhamnetin → ~sc 0.88 / bc 0.51. Engine path run_live(structure={target_sequence,
   ligand_smiles}); a ≥25-aa sequence in the query triggers a structure-only fold.

Hard rules: honesty — label REAL vs 🧪 SIMULATED vs CAPTURED everywhere; never present simulated as real or
a captured envelope as a fresh live drive; EMET/Boltz abstain rather than fabricate. Data boundary: only
public identifiers leave to EMET/Boltz/web. Q-Models GPU/AWS is SET ASIDE; Boltz via its hosted API.
Don't gate/merge — flag issues to Head Claude. Confirm you read the docs + the real/simulated state, then
bring up the demo and run it.
```

## Data you need (READ THIS — it determines which profiles work for you)
The **live** profiles (real-time moat / EMET / Boltz) need gitignored files under `RohanOnly/` that are
**local to Rohan's device and NOT in git**: `RohanOnly/moat/moat.sqlite` (58 MB), `RohanOnly/boltz_api.env`
(the Boltz key), `RohanOnly/emet_creds.env` + `RohanOnly/emet_profile/` (EMET auth).
- **If you do NOT have them** (likely, if you're on your own machine): the demo still works fully via the
  **committed frozen REAL captures** — the `Replay (captured TSC2 · $0)` and
  `Replay (TSC2 · session-bridge EMET · $0)` profiles render a real run (real moat + real EMET PMIDs +
  the real haiku persona spread), $0, no `RohanOnly/` needed. Plus `Demo (mock backends)`. These give a
  fully-real-*looking*, honest demo of your UI.
- **For the true live profiles**, ask Rohan/Head Claude to share the `RohanOnly/` data, or run on Rohan's
  device. State honestly in the demo which profile you used (live vs replay vs mock).

## Coordination (multiple live sessions right now)
- **Head Claude (Rohan's)** = approver/gater (don't touch its PRs/worktrees).
- Another **Demo Claude** may be on `:8000`. **Use a different port** (`--port 8002`). Don't touch other
  sessions' ports, worktrees, or `/tmp/*` work.
- Branch only if you must change something, and ship via PR for **Head Claude** to review — but the demo
  itself needs no code change (it's all merged).

## Definition of done
A working demo you can show: your redesigned front-end up, a TSC2 run rendering the full firm (moat +
EMET PMIDs + the spread + synthesis), honestly labeled (live vs replay vs mock). Report what worked, which
profile/data you used, and any gaps (especially if you lacked `RohanOnly/` data).

## Constraints
Honesty (REAL / 🧪 SIMULATED / CAPTURED labeled); data boundary (public identifiers only leave); no
fabrication; Q-Models GPU/AWS set aside; Boltz via hosted API. Do **not** gate/merge — that's Head Claude.
