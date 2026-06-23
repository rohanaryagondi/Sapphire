# Build Ledger

Append-only log of what shipped to `main`. Newest at the top. One entry per feature-sized change. Format:

```
## <date> — <title>   (<commit range or SHA>)
- What: one-paragraph summary.
- Gates: tests <N> green · review <verdict> · verify <verdict> · whole-branch <verdict>.
- Gaps/Follow-ups: anything deliberately deferred.
```

---

## 2026-06-23 — gnomAD constraint seam (quant-fact-seams PR-A pilot)  (`main`, PR #6)
- **Built-By: `hayes`** · merged by `rohan`. **First contributor PR — the harness's first external contribution.**
- What: stdlib-only Bucket-1 fact seam wrapping gnomAD's public GraphQL constraint API (`tools/gnomad_constraint_seam.py`)
  — emits cited **T1** facts (pLI, LOEUF, missense Z) with provenance `gnomad`, fires on a target gene symbol,
  degrades honestly (gene-not-found vs backend-error distinguished; never raises; never fabricates). Harness
  agent + complete `output_schema` (incl. `error`; `additionalProperties:false`), `data_boundary` guardrail,
  wired into `_BUCKET1_AGENTS` + `python_fns`. The pilot that locks the pattern for GTEx/InterPro/g:Profiler.
- Gates (approver, independent subagents): Gate 1 **294 green** (+16) · Gate 2 reviewer **Approved** (2 Minor
  nits → folded into the brief for the next seams) · Gate 5 verifier **PASS** (gnomAD fact lands via `run_live`,
  status `ok`, real numbers; **schema-completeness adversarial check passes — aso-tox trap NOT replicated**;
  data boundary structurally enforced; live API matches fixture) · provenance `gnomad` allowed; no secrets.
- Process: Hayes's Claude used `dev/HELP.md` correctly to flag 3 pre-existing cross-platform test conditions
  (verified pre-existing on clean main, scoped out) — answered + logged as `crossplatform-test-hardening` backlog.
- Gaps/Follow-ups: next seam = **GTEx (PR-B)**, then InterPro, g:Profiler — each its own PR off the pilot template.

## 2026-06-23 — Repo streamline + Hayes seam task + help desk + audit skill  (`main`, PR #5)
- Built-By: `rohan` · merged by `rohan`. Feature tier (docs/process/tooling; no engine code).
- What: (1) **Top-level cleanup** — top level now only `CLAUDE.md`+`README.md`; research-foundation docs →
  `docs/foundation/`, point-in-time reports → `docs/reports/`; every reference fixed (build scripts, CLAUDE.md
  Map, README, docs/README, sapphire-cascade links, REPORT.md's own links). (2) **quant-fact-seams reassigned
  to hayes**, rescoped to the clean-API set (gnomAD, GTEx, InterPro, g:Profiler), pilot-gate sequencing; brief
  rewritten as a self-contained, build-ready plan (seam template + worked gnomAD example + schema lesson +
  Gate-5). (3) **`dev/HELP.md`** — async Claude-to-Claude help desk, wired into the harness + a new
  CONTRIBUTOR_RULES rule 9. (4) **`sapphire-audit` admin skill** + `dev/audit-repo.sh` (macOS/bash-3.2-safe,
  python3 link parser) — found + fixed 2 broken doc links (1 a regression from the move).
- Gates: Gate 1 278 green · independent review **Approved-with-nits** (all 6 fixed) · whole-branch **Ready to
  merge** · Gate 5 verifier **PASS** (audit clean, 0 broken links, adversarial link-check discriminates, exit
  codes both directions, build-script paths resolve) · no secrets/binaries.
- Gaps/Follow-ups: `_build/build_xlsx.py` `CHECKLIST` is still a Windows abs path (pre-existing; only matters
  if regenerating the xlsx from raw input — not exercised). Hayes builds the seams next (gnomAD PR-A first).

## 2026-06-23 — Task assigned: quant-fact-seams (planning)  (`main`, PR #4)
- Built-By: `rohan` · merged by `rohan`. Planning/docs only — no code.
- What: Brief + workboard assignment for 6–10 quantitative-fact Bucket-1 seams (gnomAD constraint, GTEx,
  DepMap, AlphaMissense, ± Foldseek/InterPro/enrichment) in the `aso-tox` seam pattern — hard numbers that
  complement EMET's narrative. Reimplement select ToolUniverse Apache-2.0 wrappers as our own stdlib (`urllib`)
  seams; no ToolUniverse runtime, no Slurm. Brief: `docs/superpowers/plans/2026-06-23-quantitative-fact-seams.md`.
- Gates: docs tier (suite untouched, 278). Implementation ships incrementally (gnomAD pilot first), each seam
  its own Standard-tier PR with Gate-5 proof the fact lands in the dossier via `run_live`.

## 2026-06-22 — Local enforcement hardening + vision + status/workboard  (`main`, PR #3)
- Built-By: `rohan` · merged by `rohan`.
- What: Repo stays **free, no GitHub Actions** (Rohan's call) → enforcement is fully local. Added
  `.githooks/pre-commit` (bio-safe secret scanner — AWS pattern word-bounded + digit-required so protein/DNA
  sequences don't false-positive); `pre-push` now runs the full suite (`dev/run-tests.sh`) on any Python
  change; `dev/audit-history.sh` is the detective backup (Built-By coverage since the convention + secret
  leaks), replacing the dropped CI; removed `dev/ci/`. Recorded Hayes (`@HayesStewart-QuiverBS`) + Gavin
  (`@GavinWongYF`) as write collaborators. Added **`docs/VISION.md`** and the **`status/`** directory
  (OVERALL + per-area + `WORKBOARD.md` per-agent assignments, Hayes/Gavin empty for now); `dev/DELEGATION.md`
  slimmed to the protocol pointing at the workboard.
- Gates: Gate 1 278 green (`dev/run-tests.sh`; no runtime code touched) · independent review
  **Approved-with-nits** (all fixed) · Gate 5 guards RUN & verified (fake gh-token / real AWS-key / aws_secret
  form BLOCKED; clean file + protein sequence ALLOWED; scanner self-exclusion; audit CLEAN; run-tests green) ·
  no secrets/binaries.
- Gaps/Follow-ups: enforcement is per-clone + `--no-verify`-bypassable (documented hard violation; audit
  catches it) — accepted residual risk of a free repo. No work assigned to Hayes/Gavin yet.

## 2026-06-22 — Strict branch enforcement + repo renamed to Sapphire  (`main`, PR #2)
- Built-By: `rohan` · merged by `rohan`.
- What: Canonical repo renamed to **`rohanaryagondi/Sapphire`**. Layered branch-rule enforcement, as strict as
  the free tier allows: client-side `.githooks/pre-push` (blocks main/protected pushes, enforces `<handle>/`
  naming + prefix==`sapphire.handle`, blocks when unset, lets tags through) and `.githooks/commit-msg`
  (requires a real `Built-By` trailer parsed via `git interpret-trailers`, cross-validated against the clone's
  handle; tight merge exemption); `dev/setup-contributor.sh` wires both; `dev/CONTRIBUTOR_RULES.md` binds
  hayes/gavin agents. CODEOWNERS → `@rohanaryagondi`. A detective `branch-guard` Action was authored but
  **parked in `dev/ci/`** (injection-safe) — GitHub Actions can't allocate a runner on this free private repo
  (jobs fail in ~4s with no steps), so an active workflow would red-X every PR; it activates with Pro.
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
