# Build Ledger

Append-only log of what shipped to `main`. Newest at the top. One entry per feature-sized change. Format:

```
## <date> — <title>   (<commit range or SHA>)
- What: one-paragraph summary.
- Gates: tests <N> green · review <verdict> · verify <verdict> · whole-branch <verdict>.
- Gaps/Follow-ups: anything deliberately deferred.
```

---

## 2026-06-22 — Strict branch enforcement + repo renamed to Sapphire  (`main`, PR #2)
- Built-By: `rohan` · merged by `rohan`.
- What: Canonical repo renamed to **`rohanaryagondi/Sapphire`**. Layered branch-rule enforcement, as strict as
  the free tier allows: client-side `.githooks/pre-push` (blocks main/protected pushes, enforces `<handle>/`
  naming + prefix==`sapphire.handle`, blocks when unset, lets tags through) and `.githooks/commit-msg`
  (requires a real `Built-By` trailer parsed via `git interpret-trailers`, cross-validated against the clone's
  handle; tight merge exemption); `dev/setup-contributor.sh` wires both; `.github/workflows/branch-guard.yml`
  (detective backstop — fails bad PR branch names, files an issue on direct main pushes; injection-safe);
  `dev/CONTRIBUTOR_RULES.md` binds hayes/gavin agents. CODEOWNERS → `@rohanaryagondi`.
- Gates: hooks functionally verified twice (push-to-main/wrong-name/wrong-prefix/unset-handle BLOCKED,
  own-branch + tags ALLOWED; commit without real `Built-By`, body-prose evasion, fake-"Merge", cross-handle
  all REJECTED; real trailer + real merge ACCEPTED; real `git push --dry-run` to main blocked end-to-end) ·
  independent review **Approved-with-nits** (all fixed) · independent verify **PASS** · injection-safe workflow.
- Gaps/Follow-ups: true server-side branch protection still needs **GitHub Pro** (free-tier 403) —
  `dev/enable-branch-protection.sh` applies it once upgraded; `--no-verify` is a known bypass (documented hard
  violation, caught by the Action). Need Hayes/Gavin GitHub usernames before granting collaborator access.

## 2026-06-22 — Collaborative dev harness (multi-contributor, PR-gated)  (`main`, PR #1)
- Built-By: `rohan` · merged by `rohan`.
- What: Turned the solo `dev/` harness into a 3-contributor harness (rohan · hayes · gavin), each driving
  their own Claude. Git-native attribution (branch prefix `<handle>/<slug>` + `Built-By` commit trailer +
  `dev/CONTRIBUTORS.md`); `dev/DELEGATION.md` task board + claim protocol; `dev/PR_REVIEW.md` approver
  playbook; `.github/CODEOWNERS` + PR template (gate-evidence checklist); tracked `dev/reports/<handle>/`
  (inaugural ASO-tox report migrated in). Refreshed README/METHODOLOGY/CONVENTIONS/GATES + root CLAUDE.md to
  the multi-contributor, `main`-is-bedrock model. Branch surgery: old `main` → `main-backup-2026-06-22`;
  `main` fast-forwarded to the former `Rohan` bedrock; `Rohan` retired. Dogfooded via PR #1.
- Gates: 278 tests green (docs/config-only; runtime untouched) · independent review **Approved-with-nits**
  (all findings fixed) · whole-branch integrator **Ready to merge** · no secrets/binaries.
- Gaps/Follow-ups: **GitHub branch protection BLOCKED** — private free-tier repo returns 403 for protection
  + rulesets; the sole-approver rule is convention + CODEOWNERS routing until a plan upgrade / paid Quiver
  org (decision surfaced to Rohan). Do NOT grant Hayes/Gavin write access until enforcement is resolved.
  Need Hayes/Gavin GitHub usernames. CI automation of gates is future scope.

## 2026-06-22 — ASO sequences wired into `run_live` → live aso-tox dossier facts  (Rohan)
- What: Gave `run_live(query, *, sequences=None, ...)` a sequence-input channel — the documented handoff point for the future ASO-Design tool. Sequences (explicit param, else a strict `\b[ATGC]{15,}\b` query-text extractor) thread into Bucket-1 `inputs`, so the `aso-tox` agent scores them and emits real GBR T2 facts (provenance `aso-tox`) into `discover["dossier"]`. Hardened the seam (`tools/aso_tox_seam.py`) to validate input: non-ATGC sequences are rejected (never scored), surfaced honestly in `invalid_sequences`; lowercase atgc normalized to uppercase. Extended the `aso-tox` `output_schema` in `harness/agents.json` (`invalid_sequences`+`error`, `additionalProperties:false` retained) — the load-bearing fix without which the harness silently abstained on any output carrying rejected sequences (would have dropped valid facts in the mixed case). First exercise of the dev harness (`dev/`).
- Gates: **278 tests green** · review **Approved** (independent sonnet reviewer, 3 rounds) · verify **PASS** (independent sonnet verifier RAN `run_live`: happy path 2 facts with GBR numbers matching the direct seam call; mixed valid+garbage → exactly 1 fact, status `ok`; all-garbage → 0 facts no crash; honest-empty intact; schema change proven load-bearing) · Gate 3 provenance `aso-tox` (allowed) + no secrets/binaries · Gate 4 stdlib-only runtime (`re` added) + vendor `predict.py`/`.pkl` untouched. Standard tier (no Gate 6).
- Gaps/Follow-ups: wire `run_live` to the front door (`serve.py`/Console — separate keystone task); chain the ASO-Design tool to feed its designed sequences into this channel when it lands; consider upstream sanitization of empty/whitespace strings before the seam.

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
