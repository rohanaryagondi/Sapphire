# Report — Experiment Design tool, ED-1 (PR-E1): port + fidelity-lock

**Built-By:** hayes · **Branch:** `hayes/experiment-design-port` · **Task:** `experiment-design` epic, **ED-1** ·
**Tier:** Standard · **Date:** 2026-06-24 · **Source:** `vendor/design-form-agent/` (Matt Carey, Quiver).

## What this delivers
Phase-1 ED-1: ports Matt Carey's `design-form-agent` into Sapphire as a **standalone Quiver tool** at
`tools/experiment_design/`. It turns an Otter meeting transcript (`.pdf`/`.txt`) into a structured
experiment-design plan — JSON (each leaf a `{value, confidence, source}` triple) + a Markdown summary — via
Claude. The proprietary domain content is preserved **verbatim**; only the plumbing is adapted. The original's
Slack bot is **not** ported. Engine/firm wiring is a later epic — this is a standalone tool (like `tools/aso_tox/`).

## Files
| File | Change |
|---|---|
| `tools/experiment_design/extract.py` | **new (adapted)** — `extract(path)->dict`, `render_md(data)->str`, CLI. `anthropic` imported **lazily inside `extract()`** (engine/tests stay import-safe; engine stays stdlib-only). Honest `ExtractionError` on missing/empty/unsupported input, missing `ANTHROPIC_API_KEY`, or non-JSON / empty model output — never fabricates a plan. Data-boundary docstring. |
| `tools/experiment_design/extraction_prompt.py` | **new (verbatim + attribution header)** — system prompt + Quiver assay vocabulary + `MENUS_REFERENCE` + the JSON template (the live output contract). Character-for-character from vendor. |
| `tools/experiment_design/schema.py` | **new (verbatim + attribution header)** — reference dataclasses (documentation; not imported by the code). |
| `tools/experiment_design/{__init__.py, README.md, requirements.txt}` | **new** — package marker; usage + attribution + data-boundary note; `requirements.txt` = `anthropic` only (tool subprocess; PDF goes to Claude directly, no pypdf). |
| `tools/experiment_design/sample_extraction_jan6.json` | **new** — golden example output (byte-copy of the vendored sample); the fidelity fixture. |
| `sapphire-orchestrator/tests/test_experiment_design.py` | **new** — fidelity locks + honest-error + key-gated live test. |

## Fidelity & boundary (the things that matter here)
- **Verbatim preservation (CONVENTIONS §4):** the test asserts the vendored `extraction_prompt.py` / `schema.py`
  appear character-for-character inside the ported copies (only a prepended attribution header differs; 0 suffix
  bytes; under universal-newline read so LF/CRLF is immaterial). `vendor/design-form-agent/` is kept untouched as
  the canonical reference. No domain value paraphrased or dropped.
- **Engine stays stdlib-only:** `anthropic` is imported lazily inside `extract()`; the Sapphire engine imports
  nothing from the tool (grep-confirmed). Verified empirically: `import extract` succeeds with `anthropic` absent.
- **Data boundary (§3):** the tool sends transcripts ONLY to Claude (allowed — the reasoning LLM) + reads/writes
  ONLY local files; never to EMET / web / public DBs. Stated in the module docstring + README.
- **Anti-fabrication:** every bad-input class raises `ExtractionError` *before* any LLM call; the CLI prints a
  clean `ERROR:` and exits 2 (no traceback, no invented plan).

## Gate evidence (run locally on `hayes/experiment-design-port`)
- **Gate 1 — full suite GREEN: 381 tests** (`bash dev/run-tests.sh`; +13 ED-1 tests in the `tests` suite).
- **Gate 2 — independent review: Approved.** No Critical/Important. 3 Minors: (1) CRLF→LF normalization —
  cosmetic, the verbatim lock is line-ending-insensitive by design, left as-is; (2) CLI printed "Calling
  Claude…" before validation — **fixed** (removed the misleading pre-print); (3) `msg.content[0].text` could
  raise on an empty/non-text response — **fixed** (guarded → `ExtractionError`).
- **Gate 3 — provenance/secrets/binaries:** no secrets (clean scan); no binaries added by this PR (the vendored
  transcript PDFs were committed by rohan in the snapshot; the test references them, doesn't copy them).
- **Gate 4 — stdlib-only runtime:** the only third-party dep is `anthropic`, lazy-imported in the tool's
  subprocess; the engine path gains nothing.
- **Gate 5 — functional verification: Works as claimed** (independent verifier). Suite green (13, 1 live skip);
  all 4 CLI honest-error paths exit 2 with clean messages; `render_md` produces correct Markdown offline (all 3
  golden experiment names + Action Items/Open Questions); verbatim containment confirmed; engine import-safe
  without anthropic. The live LLM extraction is **correctly skipped** (no `ANTHROPIC_API_KEY` in this env) — its
  no-key behavior is covered by the honest key-error path.

## Notes / next
- The live extraction path (`extract()` calling Claude) is exercised by the key-gated `TestLiveExtraction`;
  it skips cleanly without `ANTHROPIC_API_KEY` (brief-sanctioned). Set the key + `pip install anthropic` in the
  tool's subprocess to run it against `vendor/.../test_data/*.pdf`.
- **ED-2 (PR-E2)** is next after this merges: turn the extracted JSON into the filled design sheet (JSON + MD,
  + the real `.xlsx` if the template is obtainable — coordinate via HELP). Moat/firm integration is a later epic.
