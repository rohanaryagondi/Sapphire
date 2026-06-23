# Task Brief (Epic) — Experiment Design tool (port Matt's design-form-agent into Sapphire)

**Owner: `hayes`** · Tier: **Feature epic** (multiple Standard-tier PRs) · Assigned 2026-06-23 ·
**Starts AFTER `quant-fact-seams` (GTEx/InterPro/g:Profiler) is done.**
This brief is self-contained. Follow `dev/CONTRIBUTOR_RULES.md` + `dev/METHODOLOGY.md`. Stuck on a contract,
the LLM transport, or the design-sheet template? Use `dev/HELP.md` — don't guess.

---

## The vision (where this is going)
Sapphire is becoming the **all-in-one AI for Quiver**. One thing a Quiver scientist will ask: *"read these
meeting notes and design the experiment"* — Sapphire extracts the intent from the notes and **fills the
experiment design sheet**. Eventually it will also consult internal history (the moat) and the rest of the
firm to refine the design. **This epic is PHASE 1 only: a standalone tool, meeting-notes → filled design
sheet.** Moat/firm integration is explicitly a LATER phase (see "Out of scope / future").

## What we're doing
**Port Matt Carey's `MatthewCarey24/design-form-agent` into the Sapphire repo as a first-class Quiver tool**
under `tools/experiment_design/`. We consume his full repo — nothing depends on his repo afterward (it was an
info transfer; it's Quiver-owned IP, authored by `matthew.carey@quiverbioscience.com` — preserve attribution).

**What his tool is** (verified 2026-06-23): a single-turn LLM extraction pipeline. Input = a Quiver meeting
transcript (Otter.ai PDF or plain text). It calls Claude with a system prompt hard-coded to Quiver's
optogenetics assay vocabulary (QuasAr/CheRiff constructs; NGN2/DLX2 iPSC neurons; excitability vs synaptic
assays; 96-well Ibidi; Tyrodes/BrainPhys; DAP5/NBQX/GABAzine; Viaflo/Mini-Janus addition protocols; a
`MENUS_REFERENCE` block of valid design-form dropdown values). Output = structured JSON matching Quiver's
experiment-design form: `experiments[]` each with `metadata / culture / imaging / treatments / plate_layout /
timeline / analysis_notes`, where every leaf field is a `{value, confidence: high|medium|low|unresolved,
source}` triple, plus `action_items[]` and `open_questions[]`. It also renders a markdown summary. (His repo
also has a Slack bot — **out of scope**, see below.)

## ⚠️ Data boundary — read this carefully (it is NOT what you think)
Meeting notes are **internal Quiver data**. Sending them to **Claude (the reasoning LLM)** is **allowed** —
the personas already send dossier content to Claude; the LLM is Sapphire's reasoning engine, not an external
evidence source. The data boundary forbids leaking internal data to **external evidence/data sources**
(EMET, public web, public databases, Q-Models). This tool calls **only** the LLM and touches **only** local
files. It must **never** send meeting-note content to any web/EMET/public-DB path. State this in the tool's
module docstring so it's unambiguous.

---

## Phase 1 — the work (each is its own Standard-tier PR off `main`)

### ED-1 — Port + fidelity-lock  (PR-E1; build first)
Bring Matt's code into `tools/experiment_design/`, adapted to our conventions:
- `extract.py` (core: `extract(path) -> dict`, `render_md(data) -> str`, CLI), `extraction_prompt.py` (the
  system prompt + Quiver vocabulary + `MENUS_REFERENCE`), `schema.py` (the form schema), and his
  `sample_extraction*.json` + a sample transcript as the **golden fixture**.
- **Preserve the scientific content verbatim** — the assay vocabulary, `MENUS_REFERENCE`, and the extraction
  prompt are the proprietary value (CONVENTIONS §4 vendor-verbatim analog). Wrap/adapt the plumbing; do **not**
  edit the domain prompt or menu values. Keep his original files as the canonical reference + an attribution
  header (`Ported from MatthewCarey24/design-form-agent — Matt Carey, Quiver`).
- **Golden-value test:** running the tool on Matt's sample transcript reproduces his `sample_extraction.json`
  (the fidelity lock). Since the LLM is non-deterministic, lock what's stable: schema shape, required fields,
  the `{value,confidence,source}` structure, and key extracted values present in his golden output. (If exact
  text match is infeasible, assert structural + key-field equality and document why.)
- **LLM transport (the one real decision — flag in HELP.md if unsure, but here's the call):** keep Matt's
  Anthropic-SDK approach **inside the tool's subprocess** (key-gated by `ANTHROPIC_API_KEY`), so the engine
  stays stdlib-only and his fidelity is preserved. Tests that need a live LLM call **skip cleanly** when the
  key is absent (exactly like aso-tox skips without sklearn / gnomAD's live test skips offline). A future PR
  may swap the transport to the repo's existing headless `claude -p` path (`serve.py`) — not now.
- Runnable: `python tools/experiment_design/extract.py <transcript.pdf|.txt> [--out-dir ...]`.
- DoD: code ported + attributed; golden fixture committed; golden-value test green (or cleanly skipped w/o
  key); honest errors (bad/empty input → clear error, never a fabricated plan); README in
  `tools/experiment_design/`; report in `dev/reports/hayes/`.

### ED-2 — Fill the design sheet  (PR-E2; after ED-1 merges)
Turn the extracted JSON into the **filled design sheet**, "as good as Matt's" and better where we can:
- Always produce: the filled-form **JSON** (Matt's schema) + a human-readable **design doc** (`.md`) with the
  rationale and the `{value,confidence,source}` provenance surfaced per field.
- **Write the real Excel design sheet** if the template is obtainable: use `openpyxl` (in the tool subprocess,
  not the engine) to populate Quiver's `.xlsx` design template, validating values against `MENUS_REFERENCE`
  dropdowns. **Coordination needed:** the canonical `.xlsx` template + where filled sheets should land — raise
  via `dev/HELP.md` (Rohan/Matt). If the template isn't available yet, ship JSON+MD and leave a clean
  `write_xlsx(...)` seam + a skipped test; don't block ED-2 on the template.
- DoD: filled JSON + design MD for the golden fixture; xlsx writer (or stubbed-with-skip if template pending);
  menu-validation test (invalid dropdown value is caught, not silently written); report.

---

## Out of scope / future (do NOT build in this epic)
- **Moat + firm integration** — consulting previous internal experiments (the moat) and running the proposed
  design through Bucket-1/Bucket-2 to refine it. This is the big "later" the vision points at; a separate epic.
- **Engine wiring** — making it a `run_live` Bucket-1 agent / a "design mode" query type. Phase 1 is a
  standalone tool. (When we do wire it, it'll be a `tools/experiment_design_seam.py` in the aso-tox pattern.)
- **The Slack bot** (`app.py`) — Matt's bot stays in his repo; we don't run a Slack listener in Sapphire.
- **Otter.ai API calls** — we consume transcripts as files; we don't call Otter.

## Constraints (binding)
- Engine stays **stdlib-only**: the tool's deps (`anthropic`, `pypdf`, `openpyxl`) live in the tool's own
  subprocess/install, never imported by `sapphire-orchestrator/` engine code. (Same posture as `tools/aso_tox/`.)
- Preserve Matt's domain prompt/vocabulary/menus verbatim; attribute the port.
- Never fabricate a plan on bad input; degrade honestly. No secrets/binaries (no API keys committed).
- `Built-By: hayes` on every commit; one PR per ED-step; full Gates 1–5 each.

## Definition of Done (epic, phase 1)
- [ ] ED-1 merged: tool ported + attributed, fidelity-locked by a golden test, runnable, key-gated/skip-clean.
- [ ] ED-2 merged: filled design sheet (JSON + MD; xlsx if template available, else clean seam+skip).
- [ ] `status/tools.md` lists the experiment-design tool (what it does, provenance, internal-only boundary note).
- [ ] Workboard rows flow assigned → in-progress → merged per ED-step; ledger entries at each merge.
