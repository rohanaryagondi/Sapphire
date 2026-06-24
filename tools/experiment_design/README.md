# Experiment Design tool (ED-1)

Turns a Quiver experiment-planning **meeting transcript** (Otter.ai PDF or `.txt`) into a
structured **experiment design plan**: JSON matching Quiver's design-form schema (each leaf a
`{value, confidence, source}` triple) + a readable Markdown summary with confidence flags.

**Ported from** `MatthewCarey24/design-form-agent` (Matt Carey, Quiver,
`matthew.carey@quiverbioscience.com`) — `vendor/design-form-agent/VENDORED.md` holds the canonical
unmodified snapshot. The domain prompt, `MENUS_REFERENCE`, and schema are preserved **verbatim**
(`extraction_prompt.py`, `schema.py`); only the plumbing (`extract.py`) is adapted. The original's
Slack bot (`app.py`) is **not** ported.

## Data boundary (dev/CONVENTIONS.md §3)
Meeting transcripts are internal Quiver data. This tool sends them **only to Claude** (the
reasoning LLM, via the Anthropic SDK) and reads/writes **only local files**. It never sends
transcript content to an external evidence source (EMET / web / public databases). Sending
internal notes to the reasoning LLM is allowed — the personas already do.

## Runtime posture
A standalone Quiver tool (like `tools/aso_tox/`): the `anthropic` dependency lives in **this tool's
subprocess** and is imported lazily inside `extract()`. The Sapphire engine stays **stdlib-only**
and imports nothing here. Engine/firm wiring is a later epic — Phase 1 is a standalone tool.

## Usage
```
pip install -r tools/experiment_design/requirements.txt
set ANTHROPIC_API_KEY=...        # (export on macOS/Linux) — required for a live run
python tools/experiment_design/extract.py path/to/transcript.pdf [--output-dir ./out]
```
Accepts a `.txt` transcript or a `.pdf` (sent to Claude directly). Writes
`<name>_extraction.json` and `<name>_extraction.md`. Honest failures (missing / empty / unsupported
input, missing API key, non-JSON model output) raise a clear `ExtractionError` and exit non-zero —
the tool never fabricates a plan.

## Files
| File | What |
|---|---|
| `extract.py` | Adapted core: `extract(path)->dict`, `render_md(data)->str`, CLI. |
| `extraction_prompt.py` | **Verbatim.** System prompt + Quiver assay vocabulary + `MENUS_REFERENCE` + the JSON template (the live output contract). |
| `schema.py` | **Verbatim.** Reference dataclasses describing the output shape (documentation; not imported by the code). |
| `sample_extraction_jan6.json` | Golden example output — the fidelity fixture. |

## Fidelity lock
`sapphire-orchestrator/tests/test_experiment_design.py` asserts: the ported domain content is
byte-verbatim against `vendor/design-form-agent/`; the golden sample conforms to the JSON contract
(`experiments[]` with `metadata/culture/imaging/treatments/plate_layout/timeline`, `{value,
confidence, source}` leaves, `action_items`, `open_questions`); and a key-gated live test runs
`extract()` on a vendored transcript (skips cleanly without `ANTHROPIC_API_KEY`).

## ED-2 — fill the design sheet (`fill.py`)
Turns ED-1's extracted plan JSON into the **filled design sheet**:
```
python tools/experiment_design/fill.py path/to/plan_extraction.json [--output-dir ./out] [--xlsx-template path]
```
Writes `<name>_design_sheet.json` (the plan **untouched**, plus an additive `design_sheet` block) and
`<name>_design_sheet.md` (the ED-1 render + a **Design Sheet Validation** section). Pure local transform — no
network, no LLM, stdlib-only.

**Menu validation is conservative by design.** Values for closed single-select dropdowns (Assay Types, Sub-Assay
Types, Imaging Buffers, Temperature Options) are checked against `MENUS_REFERENCE` by **exact** string match. An
off-menu value is **flagged for human review — never silently written or auto-coerced** — so a flag may be a
*formatting* mismatch (case/whitespace, e.g. `"synaptic"` vs `"Synaptic"`, or free-text elaboration such as
`"Tyrodes (modified with KMeSO4)"`) rather than a wrong value. Open menus (`…and others`) and null values never
flag. The real `.xlsx` writer is a pending seam (`TemplateUnavailable`) awaiting Quiver's template + cell map
(see `dev/HELP.md`: `experiment-design-ed2-xlsx-template`).
