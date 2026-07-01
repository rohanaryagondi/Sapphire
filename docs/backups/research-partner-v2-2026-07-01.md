# Backup — Sapphire Research Partner v2 (2026-07-01)

**Restore point taken before the overnight AWS-GPU-endpoint + Phase 5 shift.** This is the current
working localhost app with the full synthesized report — the state to fall back to if the overnight
work goes wrong.

| | |
|---|---|
| **Commit** | `994bf7b` (main) |
| **Tag** | `research-partner-v2-2026-07-01` |
| **Backup branch** | `rohan/backup-v2-2026-07-01` (never delete / force-push) |
| **Prior backup** | v1 = `ui-v1-2026-06-30` / `rohan/backup-ui-v1-2026-06-30` |

## Restore
```bash
git fetch origin --tags
git checkout research-partner-v2-2026-07-01           # read-only look
git checkout main && git reset --hard research-partner-v2-2026-07-01   # revert main (destructive)
```
Run: backend `cd frontend2 && SAPPHIRE_NO_STEP_SUMMARY=1 python server.py --port 8201` ·
web `cd web && npm install && npm run build && npx next start -p 3000` · open `localhost:3000`.

## What v2 contains (on top of v1)
- **Main-chat follow-up** over a run's stored evidence (`/api/followup`, honesty-guarded, citation pills,
  robust real-Claude JSON parse) — WO-9 Phase 1 (#158/#159).
- **Live run: real + streamed** — real partner reasoning on `profile=live` (no placeholders);
  the synthesized report **streams as it writes** (`report.py` `on_chunk` → SSE `report:chunk`); Phase 2 (#165).
- **Real local tools + inspectable detail** — semantic agents + Q-Models local-cpu plumbing (honest `stub`
  until Quiver joblibs land); Phase 3 (#166).
- **AWS GPU dry-run wiring** — GPU-tier tools route through the launcher; `SAPPHIRE_QMODELS_LIVE` opt-in;
  dry-run default; Phase 4 (#164).
- **Robust planner** (`planner.py`) — comparisons/rankings/SMILES/ASO/multi-gene; Phase 6 (#167).
- **Workspace** — rename/delete/clear-all, search, export, default profile = simulate; Phase 7 (#163).
- The full **Claude-synthesized Markdown diligence report** (report.py, sonnet, 300s, citation pills, tables).

## What's next (the overnight shift — NOT in this backup)
- **Working AWS GPU endpoint** (real tool execution via the Q-Models `aws/` recipes + HF weights).
- **Phase 5 — targeted re-invocation** (the follow-up actually runs the named agent/tool).
- Wire the local Explorer backend (Q-Models `ui/explorer/backend`) for real local-cpu DTI/BBBP/Tox.
See `dev/work-orders/WO-9-research-partner-v2.md`.
