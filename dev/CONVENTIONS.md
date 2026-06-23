# Conventions — The Binding Rules

Every change to Sapphire follows these. They are not style preferences; they are the invariants that keep a long-term, high-stakes build correct and trustworthy. A change that breaks one of these does not merge.

## 1. Repository, branches & attribution
- **`main` is the bedrock.** (As of 2026-06-22 the former `Rohan` branch *is* `main`; the pre-collaboration
  `main` is preserved at `main-backup-2026-06-22`.) **Nobody pushes directly to `main`** — all changes land via
  a reviewed PR.
  > **Enforcement model (2026-06-22)** on `rohanaryagondi/Sapphire`. The repo is a **free private** repo and
  > **stays free** — no server-side branch protection, no GitHub Actions. Enforcement is therefore **local and
  > layered**, and every clone must run `bash dev/setup-contributor.sh <handle>` to arm it:
  > 1. **`pre-commit`** — blocks staging obvious secrets (tokens/keys/.env). Backstop for §5.
  > 2. **`commit-msg`** — requires a real `Built-By` trailer matching the clone's `sapphire.handle`.
  > 3. **`pre-push`** — blocks pushes to `main`/protected branches and non-`<handle>/<slug>` branches; and if
  >    the push changes any Python, **runs the full suite (`dev/run-tests.sh`, Gate 1) and blocks on red**.
  > 4. **CODEOWNERS** routes every PR to the approver; **`dev/CONTRIBUTOR_RULES.md`** binds the agents.
  > 5. **`dev/audit-history.sh`** — the detective backup (run periodically / before trusting `main`): scans
  >    history for missing `Built-By` and leaked secrets. Replaces the (unavailable) CI check.
  >
  > **Known limitation:** the hooks are per-clone and bypassable with `git push --no-verify` — a hard
  > violation (`dev/CONTRIBUTOR_RULES.md`). Collaborators have write access, so the model relies on cooperating
  > agents + the audit backstop catching anything that slips. (`dev/enable-branch-protection.sh` remains in the
  > repo for the day this ever moves to a paid plan/org, but that is not the plan.)
- **Everyone works on a feature branch** named `<handle>/<slug>` cut from the latest `main`
  (e.g. `hayes/aso-design-tool`). The handle is your id in `dev/CONTRIBUTORS.md`.
- **Ship by opening a PR to `main`.** Contributors run the full local lifecycle (Gates 1–5) on their branch,
  then open a PR. **Only Rohan's Claude reviews, approves, and merges** (`dev/PR_REVIEW.md`).
- **The repo lives on local disk** (`~/Desktop/Projects/Quiver/sapphire-capability-map`). **Never run a live `.git` from inside a cloud-sync folder** (OneDrive/Dropbox/iCloud) — Files-On-Demand dehydration stalls git and corrupts copies. (We learned this the hard way; the repo was moved off OneDrive for exactly this reason.)
- **Conventional commits** ending with BOTH attribution trailers — the human builder and the Claude:
  ```
  Built-By: <handle>
  Co-Authored-By: Claude <model-used> <noreply@anthropic.com>
  ```
  (Use the session's model id; the stable identifier is the `noreply@anthropic.com` email, not the name.)

## 2. The runtime stays stdlib-only
- The Sapphire **engine** (`sapphire-orchestrator/`, esp. `orchestrator.py`, `live_engine.py`, `harness/`, `moat/`, `memory/`, `selfimprove/`, `trace_view.py`) imports **only the Python standard library** (`sqlite3` counts as stdlib). No pandas/numpy/sklearn/pyarrow/requests in the runtime path.
- Heavy/third-party dependencies live **outside** the engine:
  - build-time tools in `_build/` may use pyarrow (e.g. the moat ingest).
  - external predictive tools (`tools/aso_tox/`, Q-Models) run as **subprocess/delegate** seams; the engine shells out via stdlib `subprocess`+`json` and never imports their deps.
- A reviewer/verifier greps the runtime for third-party imports as part of the gate.

## 3. Provenance & data honesty
- **Every fact carries a provenance label** from the allowed set in `sapphire-orchestrator/contracts/provenance.py` (`moat-real`, `emet-live`, `qmodels:*`, `aso-tox`, `persona-judgment`, `synthesis`, `memory-recall`, `stub`, `mock`, `unavailable`, …). Emitting an unlisted label is a defect.
- **Public identifiers only leave Quiver.** Gene symbols, SMILES, public disease terms, PMIDs — yes. Internal candidate IDs (`QS\d+`), proprietary structures — never (the `data_boundary` guardrail enforces this; don't route around it).
- **Never fabricate.** No invented PMIDs, no made-up numbers. Unknowns are flagged `KNOWN_UNKNOWN`/`DIVERGENCE` with `source:"-"`, not given a fake citation. Speculation is labeled as such.
- **Degrade honestly.** A seam that can't reach its backend returns `[]`/an error envelope with honest provenance — it never raises into the engine and never fakes a result.

## 4. Vendored/proprietary logic is preserved verbatim
- When integrating a Quiver tool or a colleague's model (e.g. Hongkang's ASO tox model), **the scientific logic is copied character-for-character** — coefficients, feature math, thresholds, rounding. We **wrap**, we do not modify.
- Keep the original artifact (notebook/model/sample) in the repo, unmodified, as the canonical reference. A golden-value test locks the wrapper to the original's outputs.
- Pin the exact dependency version the artifact was produced with (e.g. `scikit-learn==1.8.0` for the tox pkl) and record any version caveats.

## 5. Secrets & binaries
- **No secrets in git** — ever. No `.env`, keys, tokens, passwords. Scrub before commit.
- **No large binaries in git.** The moat SQLite and source parquet are gitignored (`RohanOnly/moat/`). Small essential model assets (e.g. the 124 KB tox `.pkl`) may be committed; anything large gets a build step instead.

## 6. Tests
- **Real-behavior tests**, offline and $0. Mock external LLM/EMET/AWS; run the real local pieces (the moat, the tox tool) for real where free.
- A test that needs an absent resource (built moat DB, sklearn) **skips cleanly** with a clear reason — it does not fail or silently pass vacuously.
- **No vacuous assertions.** A test that would pass on broken behavior is worse than no test (see the `must_cite_dossier` regression). Assert the substance.
- Tests live under each module's `tests/` and the top-level `tests/`.

## 7. Subagents & the controller
- **Separation of powers:** the agent that implements a change never reviews or verifies it.
- **Serialize commits.** Read-only reviewers/verifiers run in parallel; anything that writes to git runs one at a time (avoid `index.lock` races).
- **Keep the controller lean.** Delegate heavy reads (large files, diffs, zips) to subagents; the controller keeps conclusions, not bytes.
- **Models:** sonnet for implement/review/verify; opus for plan/architecture/whole-branch review.

## 8. Reporting
- Report outcomes faithfully. If tests fail, say so with the output. If a step was skipped, say so. State "done" only when it is done **and verified**.
- Flag missing inputs explicitly (e.g. "training CSVs not included") rather than papering over them.
