# Status — Fact Tools

*The fact sources the firm calls. Updated 2026-06-22.* Each carries an honest provenance label.

| Tool | State | Provenance | Notes |
|---|---|---|---|
| **EMET (BenchSci)** | ✅ live | `emet-live` | Playwright skill behind an MCP-swappable seam; cited T2 facts; never emits a formal VETO. |
| **Personas (Bucket 2)** | ✅ live | `persona-judgment` | No-tools, must-cite-dossier; independent verdicts → moderated rebuttal. |
| **Q-Models** | ✅ real | `qmodels:*` | 24 tools vendored in `q-models/`; CPU sync (`live-local`, $0); GPU via async launcher (live-proven). Some tracks marked `stub`/`eval` in `qmodels/registry.json` — never silently mocked. |
| **Internal moat** | ✅ real | `moat-real` | `MoatClient` + `moat_facts` read Loka CNS_DFP EP-distance data; degrades honestly to `[]`/mock if `RohanOnly/moat/moat.sqlite` isn't built. |
| **ASO-tox** | ✅ real | `aso-tox` | Hongkang's GBR model (`tools/aso_tox/`); stdlib seam `tools/aso_tox_seam.py`; real predictions when sequences present, honest-empty otherwise. Input validated (non-ATGC rejected). sklearn pinned 1.8.0 in the subprocess. |

## Open items
1. **ASO Design tool** — does not exist yet. Build it; its output feeds the `aso-tox` `sequences=` channel
   (the handoff is already defined in `run_live`). → backlog `aso-design-tool` (suggested: hayes).
2. **Chronic-tox model** — roadmap; scope the integration. → backlog `chronic-tox` (suggested: hayes).
3. **Retire/label remaining mocks** — audit every track; mark `proven` vs `paper-claim`; nothing silently
   mocked. → backlog `retire-mocks`.

## Watch-outs
- **Data boundary is absolute**: public identifiers only leave Quiver. Tools that call external services
  (EMET, Q-Models) must never receive internal candidate IDs or proprietary structures.
- Vendored model logic (e.g. the tox `.pkl`) is **verbatim** + golden-tested + dep-pinned (Gate 4).
