# Build Ledger

Append-only log of what shipped to `Rohan`. Newest at the top. One entry per feature-sized change. Format:

```
## <date> — <title>   (<commit range or SHA>)
- What: one-paragraph summary.
- Gates: tests <N> green · review <verdict> · verify <verdict> · whole-branch <verdict>.
- Gaps/Follow-ups: anything deliberately deferred.
```

---

## 2026-06-22 — Dev Harness established  (this change)
- What: Created `dev/` — the self-contained SDD methodology, conventions, gates, ledger, templates — plus runnable `.claude/agents/sapphire-dev-*` and the `sapphire-build` skill. Clean separation of the **dev harness** (building Sapphire) from the product **runtime harness** (`sapphire-orchestrator/harness/`). Refreshed all repo docs to current state.
- Gates: docs/process change — Gates 1–5 applied to any code touched; the harness itself dog-foods Gate 5 (a verifier confirmed the agent/skill files are well-formed and the workflow is runnable).
- Gaps/Follow-ups: adopt across all future work; consider a pre-commit hook for Gates 3–4.

## 2026-06-22 — Quiver ASO acute-tox tool integrated  (`79c1603`, `d18ae0d`)
- What: Hongkang's sequence-based ASO acute-toxicity model integrated as the callable `aso-tox` delegate. Canonical artifact in `tools/aso_tox/` (unmodified); verbatim `predict.py` runner; stdlib-only seam; harness agent + provenance `aso-tox`; wired into `live_engine` Bucket-1 (fires on ASO sequences → downstream of the future ASO Design tool). scikit-learn pinned 1.8.0 (GBR identical across 1.6.1/1.8.0).
- Gates: 268 tests green · golden-value test locks verbatim logic (Hagedorn exact, labels, GBR ordering) · stdlib runtime preserved · no secrets.
- Gaps/Follow-ups: confirm input contract + score interpretation with Hongkang; chain the ASO Design tool when it lands; chronic-tox model on the roadmap.

## 2026-06-22 — Review-driven fix pass  (`290530f`, `7c05985`)
- What: Two independent reviewers found 2 Criticals the overnight opus review missed — `must_cite_dossier` was miswired (`dossier_fields` passed in inputs, read from ctx → every persona force-abstained, roundtable was a no-op) and Q-Models output was silently dropped (no schema). Both fixed; masking tests hardened; data-honesty fixes. Roundtable verdicts 0 → 5/5.
- Gates: 252 tests green · 2-reviewer pass · 14 PMIDs verified against live PubMed.
- Gaps/Follow-ups: this is *why* Gate 5 (functional verification) exists.

## 2026-06-22 — Live harness wiring + transparency + scenarios + loop  (`e4a2bc8..9777ddd`)
- What: `live_engine.run_live` dispatches every agent + persona through `harness.run` (real moat live; other backends mockable → verified offline $0). `trace_view.py` CLI transparency. 3 new live-EMET scenarios (6 captured). Self-improvement loop running (memory/recall/blindspot/metrics).
- Gates: 250 tests green · opus whole-branch review "Ready to merge".
- Gaps/Follow-ups: wire `run_live` to the front door (serve.py/Console); real-LLM end-to-end run; broaden scenario coverage.

## (earlier) — Real internal moat; Phases 1–5
- What: Mock moat retired → real Loka CNS_DFP EP-distance substrate (`moat-real`). Earlier: the two-bucket firm end-to-end (canned), the agent harness, live EMET integration, Q-Models plumbing, the self-improvement loop. See `MORNING-REPORT.md` and `REPORT.md` for detail.
- Gates: per-task + whole-branch reviews; direction semantics verified biologically (TSC2→TSC1).
- Gaps/Follow-ups: reconcile moat rescue scoring with Loka's method (needs Loka repo + workflow doc).
