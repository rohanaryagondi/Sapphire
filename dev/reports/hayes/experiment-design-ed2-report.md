# Report — Experiment Design tool, ED-2 (PR-E2): fill the design sheet

**Built-By:** hayes · **Branch:** `hayes/experiment-design-ed2` · **Task:** `experiment-design` epic, **ED-2** ·
**Tier:** Standard · **Date:** 2026-06-24 · **Builds on:** ED-1 (PR #28, merged).

## What this delivers
ED-2 turns ED-1's extracted plan JSON into the **filled design sheet**. New module
`tools/experiment_design/fill.py`:
- **`fill(extraction) -> dict`** — the form-ready JSON: Matt's schema with the plan **preserved untouched**,
  plus an additive `design_sheet` block (`menu_validation`, `menu_ok`, `experiment_count`, `unresolved_fields`).
- **`render_design_doc(filled) -> str`** — the human-readable design doc: reuses ED-1's `render_md` for the
  per-field `{value, confidence, source}` provenance body, then appends a **Design Sheet Validation** section
  (readiness rollup + menu flags for review).
- **`validate_menus(extraction) -> list`** — the safety net: extracted values for **closed** single-select
  dropdowns (Assay Types, Sub-Assay Types, Imaging Buffers, Temperature Options) are checked against
  `MENUS_REFERENCE`. An off-menu value is **flagged for human review — never silently written** into a dropdown
  cell (the ED-2 DoD). Open menus (`…and others`) and null values never flag. Menus are parsed from the
  **verbatim** `MENUS_REFERENCE` (ED-1) so the vocabulary stays single-sourced.
- **`write_xlsx(...)`** — a clean **pending seam**: raises `TemplateUnavailable` rather than guess a cell layout.
- **CLI** — `python tools/experiment_design/fill.py <plan_extraction.json> [--output-dir] [--xlsx-template]`
  writes `<name>_design_sheet.json` + `.md`; honest `exit 2` on bad input.

## Files
| File | Change |
|---|---|
| `tools/experiment_design/fill.py` | **new** — `fill` / `validate_menus` / `parse_menus` / `render_design_doc` / `write_xlsx` (seam) / CLI. **Pure stdlib**, no network, no LLM. |
| `sapphire-orchestrator/tests/test_experiment_design_fill.py` | **new** — 23 tests (1 skipped = pending xlsx real-write). |
| `dev/HELP.md` | **+1 Open request** — `experiment-design-ed2-xlsx-template` (the canonical .xlsx template + cell map + output location). |
| `status/tools.md`, `status/WORKBOARD.md` | ED-2 status → in-review. |

## The things that matter here
- **Menu validation is real, not vacuous.** On the golden it flags **exactly one** value — exp-1
  `imaging.imaging_buffer = "Tyrodes (modified with KMeSO4)"` is not in *Imaging Buffers* {Tyrodes, Brainphys,
  Other} — and correctly passes exp-2's exact `"Tyrodes"` and all on-menu `assay_type = "Synaptic"`. Tests prove
  both directions (invalid caught + valid passes), satisfying the DoD ("invalid dropdown value is caught, not
  silently written").
- **Plan preserved.** The `design_sheet` block is purely additive; a test asserts every original top-level plan
  key is byte-equal in the output (`set(filled) - set(plan) == {"design_sheet"}`).
- **Data boundary (§3).** ED-2 does **no network and no LLM call** — a pure local transform over the already-
  extracted JSON + local files. Strictly tighter than ED-1.
- **Engine stays stdlib-only (Gate 4).** `fill.py` imports zero third-party packages at module load
  (grep-confirmed); the would-be `openpyxl` is only ever a lazy import inside the (currently non-executing) xlsx
  seam, in the tool's subprocess. The engine imports nothing from the tool.
- **Anti-fabrication.** Malformed extraction → `FillError`; missing/invalid input file → CLI `exit 2`, no
  traceback, no fabricated sheet. The xlsx writer refuses to guess a layout (`TemplateUnavailable`).

## xlsx writer — why it's a seam (not blocked)
The brief sanctions shipping JSON + MD + a clean `write_xlsx(...)` seam + a skipped test if Quiver's template
isn't available. Matt's `vendor/design-form-agent/` has **no** xlsx writer or template (only the Otter→JSON
extractor + a Slack bot), and `MENUS_REFERENCE` gives the dropdown vocabulary but not the sheet's cell layout.
Guessing the cell map risks a silently-wrong sheet, so `write_xlsx()` raises `TemplateUnavailable` and I filed
**HELP `experiment-design-ed2-xlsx-template`** for the template + cell map + output location. The real
`openpyxl` population is a small follow-up once that lands.

## Gate evidence (run locally on `hayes/experiment-design-ed2`)
- **Gate 1 — full suite GREEN: 404 tests** (`bash dev/run-tests.sh`; the `tests` suite 156 → 179, +23 ED-2; 1 skip = pending xlsx real-write).
- **Gate 2 — independent review: APPROVE-WITH-MINORS.** No blockers; the reviewer confirmed the menu logic is correct and the tests non-vacuous (off-menu flagged + on-menu passes + plan byte-preserved). 5 minors, **all applied/addressed**: (1) `parse_menus` paren-comma split → **fixed** (paren-aware `_split_options` + a parse test); (2) non-dict leaf silently skipped → **fixed** (bare-scalar leaves now validated); (3) dead `ExtractionError` re-export → **removed**; (4) redundant `.get("experiments", [])` → **simplified**; (5) exact-match is case/whitespace-sensitive by design → **README note added**.
- **Gate 3 — provenance/secrets/binaries:** clean — only new `.py` + docs, no binaries, no secrets (scanned).
- **Gate 4 — stdlib-only runtime:** `fill.py` imports no third-party package at module load; engine imports nothing from the tool (grep-confirmed).
- **Gate 5 — functional verification: WORKS-AS-CLAIMED** (independent verifier). All 6 claims confirmed by execution: normal run writes both artifacts (exit 0); the single golden flag is a real off-menu catch (exp-1 buffer) while exp-2 `Tyrodes` + all `Synaptic` correctly pass; honest `exit 2` on missing / malformed / non-dict / missing-`experiments` input (no traceback, no fabricated sheet); `--xlsx-template` → pending-seam NOTE, no file written; **import-safe with `anthropic`+`openpyxl` blocked via `sys.meta_path`** (stdlib-only proven); plan byte-equal (only `design_sheet` added). The verifier's BOM observation is folded in (input now read `utf-8-sig`).

## Notes / next
- **ED-2 is the second of the `experiment-design` epic.** After it merges: the 6 `semantic-corpora` (patent-ip,
  post-market-safety, clinical-trial-registry, payer-market-access, manufacturing-cmc, dea-scheduling). That
  task's Step 0 needs a **human BenchSci/EMET sign-in** (Playwright) — I'll flag it when I reach it.
- The `.xlsx` writer wires up once HELP `experiment-design-ed2-xlsx-template` is answered.
