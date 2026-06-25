# robyn-scs-firm-seam — wire robyn_scs into the firm as a Bucket-1 seam — report

**Branch:** `rohan/robyn-scs-firm-seam` · **Built-By:** rohan · **Tier:** Standard

## Goal
Wire the (already endpoint-wired) `tools/robyn_scs/` SCS/STA neuronal-connectivity pipeline into the
Sapphire firm as a **Bucket-1 fact seam**, mirroring `aso-tox` — heavy deps in a subprocess, engine
stays stdlib, **fires only when relevant** (imaging data present), honest-empty otherwise.

## What shipped
- **`tools/robyn_scs/firm_endpoint.py`** — a thin stdin-JSON subprocess entrypoint (the heavy-deps
  side): calls `endpoints.run_batch` and prints a small JSON **summary** (`n_fovs`, `n_connections`,
  `n_neurons`, tier breakdown, failed FOVs). No reimplementation; never raises into the caller.
- **`sapphire-orchestrator/tools/robyn_scs_seam.py`** — stdlib-only seam: `findings(inputs)`. Fires
  **only** when `inputs["robyn_scs"]` carries an `input_dir` (a `v17_traces` plate dir) → shells to
  `firm_endpoint.py`, maps the summary to dossier facts. **Honest-empty `[]`** for a standard
  target/diligence query (no imaging data), exactly like aso-tox with no sequences. Pipeline error →
  a `KNOWN_UNKNOWN` fact, never a fabricated connectivity result.
- **Registered** `robyn-scs` (kind `python`, provenance `robyn-scs`, guards `facts_only_cited`/`stamp_provenance` —
  NO `data_boundary` (that guard is for external-fetch agents; robyn-scs is internal-plane, like moat-real)) in `harness/agents.json`; wired into
  `live_engine` Bucket-1 (`_BUCKET1_AGENTS` + ctx setdefault).
- **Provenance `robyn-scs` → INTERNAL plane** (`contracts/provenance.py`): robyn_scs facts derive
  from Quiver's own imaging — proprietary internal data, protected by `data_boundary` like `moat-real`.
  This makes robyn-scs the **second** internal-plane label; the "only moat-real is internal" invariant
  test was generalised to `_INTERNAL_LABELS = {moat-real, robyn-scs}`. **Flagged in `dev/HELP.md`** as
  a data-boundary call (the conservative direction — it tightens, not loosens, the boundary).

## Runtime posture (honest)
robyn_scs needs MATLAB-split imaging CSVs we don't have in this repo, so the seam **cannot fire with
real data here** — it is honest-empty for every standard query (incl. the TSC2 demo). The fire path
(summary → facts) is verified by a **mocked subprocess** (the brief's "verify by import/signature,
not execution"); the real-data run is an analyst-side activity once imaging CSVs are provided.

## Honesty (Head Claude Gate-5 fix)
An empty/absent plate yields zero FOV quartets — `firm_endpoint.py` returns an honest `ok:false` (not a `0 connections` success), and the seam maps it to `KNOWN_UNKNOWN` (defensive guard too). A **non-mocked** test exercises the real subprocess on an empty dir and asserts no fabricated success fact.

## Gates
- **Gate 1:** `bash dev/run-tests.sh` → GREEN (+ robyn-scs seam tests + provenance + run_live wiring).
  Offline, no subprocess/heavy-deps in CI (the seam is honest-empty without imaging input).
- **Gate 3:** robyn-scs facts are **internal plane** (data-boundary protected); no secrets; engine
  imports no third-party (seam is stdlib; numpy/scipy/pandas live in the `firm_endpoint.py` subprocess).
- **Gate 4:** `import live_engine` pulls no third-party; the vendored `robyn_scs/utils` is untouched.
- **Gate 5:** seam fires (mocked) → summarised facts; honest-empty without imaging data; pipeline
  error → KNOWN_UNKNOWN; `run_live` shows `robyn-scs` `ok` (fired honest-empty) for the TSC2 query.

## Files
- `tools/robyn_scs/firm_endpoint.py` (new) · `sapphire-orchestrator/tools/robyn_scs_seam.py` (new) ·
  `harness/agents.json` (+agent) · `live_engine.py` (+wiring) · `contracts/provenance.py` (+label,
  internal) · `contracts/tests/test_provenance.py` (invariant generalised) ·
  `tests/test_robyn_scs_seam.py` (new) · `dev/HELP.md` (data-boundary flag).
