# ASO-Tox Sequence Wiring — Implementation Report

**Task:** Feed ASO sequences into `run_live` so `aso-tox` produces dossier facts.
**Date:** 2026-06-22
**Branch:** Rohan

## What Changed

### `sapphire-orchestrator/live_engine.py`
- Added `import re` (stdlib — no new third-party deps).
- Added `_extract_aso_sequences(query) -> list[str]` helper (lines ~52-83): strict regex `[ATGC]{15,}` at word boundaries. Uppercase-only, length ≥ 15. Gene symbols (TSC2, SCN2A — contain digits or non-ATGC letters) never match. Lowercase excluded by character class.
- Changed `run_live` signature to `run_live(query, *, sequences=None, ctx=None, registry=None, engine=None)`.
- Added sequence resolution block (after engine init): explicit `sequences=` param takes precedence; if `None`, falls back to `_extract_aso_sequences(query)`. Precedence documented in comment.
- Added `"sequences": resolved_sequences` to `bucket1_inputs` dict — threads to every Bucket-1 agent including `aso-tox`.
- Added docstring comment marking this as the documented handoff point for the future ASO-Design tool.

### `sapphire-orchestrator/tests/test_live_engine.py`
Added 7 new tests in `TestAsoSequenceWiring`:
1. `test_sequences_param_produces_aso_tox_facts` — explicit sequences → ≥1 aso-tox fact with GBR/label content. Skips cleanly if sklearn unavailable.
2. `test_no_sequences_aso_tox_honest_empty` — no sequences → aso-tox dispatched, facts=[] (honest empty). No skip needed.
3. `test_extractor_detects_sequences_in_query` — positive: embedded ATGC tokens ≥15 chars are found.
4. `test_extractor_does_not_misread_gene_symbols` — negative: TSC2, SCN2A, NAV1_8, GRIN2B, mTOR → no extractions.
5. `test_extractor_ignores_short_atgc_tokens` — boundary: 14-char pure ATGC token not extracted.
6. `test_extractor_ignores_lowercase` — strict: lowercase atgc sequence not extracted.
7. `test_explicit_sequences_param_takes_precedence` — param=[] overrides extractor; query with embedded sequence yields 0 tox facts. Skips if sklearn unavailable.

## Test Results

| Suite | Before | After |
|---|---|---|
| tests/ (top-level) | 57 | 64 |
| contracts/tests | 23 | 23 |
| harness/tests | 68 | 68 |
| emet/tests | 18 | 18 |
| memory/tests | 14 | 14 |
| selfimprove/tests | 20 | 20 |
| moat/tests | 68 | 68 |
| **Total** | **268** | **275** |

All 275 green. No regressions.

## Constraints Verified
- `live_engine.py` stdlib-only: `re`, `sys`, `os` only (grep confirmed).
- Tool scientific logic (`predict.py`, `.pkl`) untouched.
- No provenance re-stamping — aso-tox provenance set by seam as before.
- Tests that require sklearn skip cleanly with explicit reason if seam returns error.

## Deviations from Brief
None. All items from the Definition of Done implemented and verified.

---

## Fix Loop — Gate 5 Findings (2026-06-22)

### Fix 1 — Sequence validation at the seam

**File changed:** `sapphire-orchestrator/tools/aso_tox_seam.py`

Added `import re` (stdlib) and `_VALID_SEQUENCE_RE = re.compile(r'^[ATGC]+$')`.

Added `_validate_sequences(sequences) -> (valid, invalid)` helper (lines ~31-55):
- Strips and uppercases each sequence before the ATGC check.
- Returns (`valid_uppercase_list`, `invalid_original_list`).
- Uppercase normalisation documented in comment: callers passing lowercase atgc are accepted (the model's encoding is uppercase ATGC); callers passing non-ATGC characters get their sequence in `invalid_sequences`, never scored.

Modified `predict(sequences)`:
- Returns `{"predictions": [], "provenance": "aso-tox", "invalid_sequences": []}` for empty input.
- Calls `_validate_sequences` before subprocess: only valid sequences go to predict.py.
- If all sequences are invalid, returns `predictions: []` with full `invalid_sequences` list — no model call, no fabricated facts.
- For partial valid: scores valid portion, merges `invalid_sequences` back into the parsed result.
- All error envelopes now carry `invalid_sequences` field.

Modified `predict_findings(inputs)`:
- Merges `invalid_sequences` from `raw` into the returned dict (only if non-empty, to avoid polluting clean results).
- Returns `invalid_sequences` on error envelopes too.

**Rejected sequences surface in:** `result["invalid_sequences"]` on both `predict()` and `predict_findings()` return dicts.

### Fix 2 — Numeric cross-check in test_sequences_param_produces_aso_tox_facts

**File changed:** `sapphire-orchestrator/tests/test_live_engine.py`

Added before the `run_live` call in test 8:
- Direct call to `aso_tox_seam.predict([ref_seq])` to obtain the real GBR score.
- Formats it as `f"{ref_gbr:.3f}"` (the same format `predict_findings` uses).
- After `run_live`, asserts that the formatted score string appears in at least one dossier fact value.
- A stub that returns formatted strings without calling the model would produce a different number and fail.

### New tests added (tests 15–17 in TestAsoSequenceWiring)

| Test | What it covers |
|---|---|
| `test_all_garbage_sequences_not_scored` | All-garbage input → 0 predictions, all in `invalid_sequences`, engine doesn't crash, 0 dossier facts |
| `test_mixed_sequences_one_valid_one_garbage` | 1 valid + 1 garbage → exactly 1 scored fact for the valid seq, garbage in `invalid_sequences` at both `predict()` and `predict_findings()` level |
| `test_seam_accepts_lowercase_atgc` | Lowercase atgc accepted + normalised; GBR score matches uppercase call; nothing lands in `invalid_sequences` |

### Test counts after fix loop

| Suite | Before fix loop | After fix loop |
|---|---|---|
| tests/ (top-level) | 64 | 67 |
| All others | 211 | 211 |
| **Total** | **275** | **278** |

All 278 green. No regressions.

---

## Controller addendum — schema fix (post-verify, the load-bearing correction)

The final Gate-5 re-verify exposed a **latent bug** that the per-task verify had missed:
the `aso-tox` agent `output_schema` in `harness/agents.json` had `additionalProperties: false`
and did NOT list `invalid_sequences` / `error`. So when the seam started surfacing rejected
sequences, the harness rejected any aso-tox output carrying those keys → repair exhausted →
agent **abstained** → valid facts silently dropped. The happy path only survived because the
implementer's *conditional* `invalid_sequences` emission omitted the key when no rejects existed;
the **mixed valid+garbage** case (1 valid + 1 garbage) would have abstained and dropped the
valid fact when run through `run_live`.

Fix (controller, then independently re-reviewed + re-verified):
- `harness/agents.json`: extended the aso-tox `output_schema.properties` with
  `invalid_sequences` (array of strings) + `error` (string); `additionalProperties: false` retained.
- `tools/aso_tox_seam.py`: `predict_findings` now ALWAYS emits `invalid_sequences` (matches the
  `predict()` contract).
- `tests/test_live_engine.py`: test 16 (mixed) now asserts end-to-end **through `run_live`**
  (status `ok` + exactly 1 dossier fact) — a true regression guard for the schema; test 9
  (honest-empty) asserts status `ok`; test 10 gains a punctuation-adjacent extractor case.

Verifier confirmed the schema change is load-bearing: the OLD schema rejects `invalid_sequences`
(`additional property not allowed`); the NEW schema accepts it; rogue fields still rejected.

Final state: **278 tests green**; Gates 1–5 all green.
