# Vendored — design-form-agent (Matt Carey)

**This is a preserved, verbatim snapshot of an internal Quiver repo, imported as the canonical reference
for the Sapphire Experiment Design tool port.** Do not edit the files here — they are the unmodified original
(CONVENTIONS §4: keep the original artifact in the repo, unmodified, as the canonical reference). The adapted,
Sapphire-integrated tool lives (will live) in `tools/experiment_design/`.

## Provenance
- **Source:** `github.com/MatthewCarey24/design-form-agent` (private, Quiver-internal).
- **Author:** Matt Carey `<matthew.carey@quiverbioscience.com>`.
- **Upstream commit:** `afcf01b62035092a76fb79443866e4e1d3a51d74` ("Meeting agent: Otter transcript -> experiment plan extractor"), 2026-06-23.
- **Imported:** 2026-06-23 by rohan (per Rohan's direction "consume his full repo into Sapphire — no dependency on his repo"). `.git` history not included; this is a flat snapshot.

## What it is
A single-turn LLM extraction pipeline: a Quiver meeting transcript (Otter.ai PDF / text) → Claude (Anthropic
SDK) with a system prompt hard-coded to Quiver's optogenetics assay vocabulary → structured JSON matching
Quiver's experiment-design form (`experiments[]` with `metadata/culture/imaging/treatments/plate_layout/
timeline`, each leaf a `{value, confidence, source}` triple), plus a markdown render. (Also ships a Slack bot,
`app.py` — out of scope for the Sapphire port.)

## Files
- `extract.py` — core: `extract(path)->dict`, `render_md(data)->str`, CLI.
- `extraction_prompt.py` — the system prompt + Quiver assay vocabulary + `MENUS_REFERENCE` (the proprietary
  domain value — **port verbatim**, do not paraphrase).
- `schema.py` — the design-form schema.
- `sample_extraction_jan6.json` + `meeting_extraction_review_jan6.md` — golden example + human review.
- `test_data/*.pdf` — real Otter meeting transcripts (golden-fidelity-test inputs).
- `generation_results/*` — real extraction outputs (reference).
- `.env.example` — env template (no real secrets; keys read from env at runtime).

## How it's used in Sapphire
The `experiment-design` epic (ED-1) ports the relevant pieces into `tools/experiment_design/`, preserving the
domain prompt / `MENUS_REFERENCE` / schema verbatim with an attribution header, locked by a golden-value test
against `sample_extraction_jan6.json`. See `docs/superpowers/plans/2026-06-23-experiment-design-tool.md`.
The Anthropic/PDF deps stay in the tool subprocess — the Sapphire engine remains stdlib-only.

## Data-boundary note
Meeting transcripts are internal Quiver data; sending them to **Claude (the reasoning LLM)** is allowed (the
personas already do). This tool touches only the LLM + local files — never an external evidence source
(EMET / web / public DBs).
