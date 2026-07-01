# Backup — Sapphire UI v1 (2026-06-30)

**Restore point taken before the "Research Partner v2" rebuild (follow-up chat + roadmap).**

This is the approved, working UI as demoed on 2026-06-30 after the full WO-8 build + the
post-ship polish round. If v2 work goes wrong, restore from here.

## What / where

| | |
|---|---|
| **Commit** | `8c49ef1` (`feat(ui): show specific Q-Models tool+input; per-agent detail for side-chat`) |
| **Backup branch** | `rohan/backup-ui-v1-2026-06-30` (never deleted / never force-pushed) |
| **Annotated tag** | `ui-v1-2026-06-30` |
| **Baseline branch** | merged to `main` on 2026-06-30 (v1 = canonical `main`) |
| **Date** | 2026-06-30 |

## How to restore

```bash
git fetch origin --tags
# inspect it
git checkout ui-v1-2026-06-30          # detached, read-only look
# OR make it live again on a branch
git checkout -b restore-ui-v1 rohan/backup-ui-v1-2026-06-30
# OR hard-reset main to v1 (destructive — only if v2 is abandoned)
git checkout main && git reset --hard ui-v1-2026-06-30
```
Then run it: backend `cd frontend2 && SAPPHIRE_NO_STEP_SUMMARY=1 python server.py --port 8201`
· web `cd web && npm install && npm run build && npx next start -p 3000` · open `localhost:3000`.

## What v1 contains (feature inventory)

- **3-pane app** (Workspace rail · chat · Trace|Info panel), Quiver-violet, no emojis, `#0d0c22` side panels.
- **Synthesized diligence REPORT** in the main column — Claude (`report.py`, sonnet, 300s timeout) writes a
  narrative report from the whole dossier: abstract → Target & mechanism → Quiver data → External evidence →
  Regulatory/IP → How the partners weighed in → Recommendation. 16px / 1.7 / ~70ch, GFM tables supported.
- **Inline `[[source]]` citation pills** (EMET · Quiver data · External Models · …) → click opens that agent's
  Info tab; single-source paragraphs cited once at the end.
- **Live Trace** — dynamic-height rows (no overlap), colored status dots (no icons), 1–2-line result summaries
  derived from each agent's facts (backend per-step LLM summarizer disabled via `SAPPHIRE_NO_STEP_SUMMARY` to
  avoid the CPU storm + free the report's Claude call).
- **Info panel** — per-agent `status · provenance · model · query (scoped target) · contributed facts · full
  detail`, scoped side-chat over that step's evidence (now incl. the full per-agent `detail`).
- **Collapsible "Cited fact dossier"** (default closed → sections → source groups → facts).
- **Q-Models** shows the SPECIFIC selected tool + input (e.g. DTI / kg_hypothesis / variant_effect).
- Chrome: ⌘K palette, Pin, run toasts, Export (Markdown). "Quiver data" (never "moat"). No "CNS decision firm",
  no "never fabricates" footer.
- Backend: `run_live` two-bucket firm; `simulate` ($0, real facts, placeholder partner reasoning) + `live`
  (real Claude) profiles; conversations persisted server-side.

## Known limits carried into v2 (the reason for the rebuild)

- Follow-ups re-run the whole firm (no evidence-scoped follow-up chat yet).
- `simulate` partner reasoning is placeholder; live runs are ~6 min.
- Report is not streamed (≈70–100s wait).

See `dev/work-orders/WO-9-research-partner-v2.md` for the v2 plan built on top of this baseline.
