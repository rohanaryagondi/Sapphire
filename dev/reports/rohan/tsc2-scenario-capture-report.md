# tsc2-scenario-capture — the real TSC2 run, frozen for $0 replay — report

**Branch:** `rohan/tsc2-scenario-capture` · **Built-By:** rohan · **Tier:** Feature

## Goal
Capture **one real `run_live`** on the TSC2 / tuberous-sclerosis query (real moat + **live EMET** +
haiku firm) and freeze it so the front end replays it **instantly, $0, deterministically** — while
reflecting the genuine run (real moat values + real EMET PMIDs + the spread + a DIVERGENCE).

## What was captured (real, contract-validated)
`_build/capture_tsc2_live.py` ran the full firm on haiku with the **live-captured EMET envelope**
injected (the 8 real PMIDs I drove from the authenticated BenchSci session in Track A) + the **real
Quiver moat**. Wall-clock **1050 s**. Output frozen to
`sapphire-orchestrator/scenarios/tsc2_live_run.json` (validates against `run_live_schema` → 0 errors):

- **65 dossier facts** — `moat-real: 8` (real internal CNS_DFP EP-signatures of *TSC2 KO*),
  **`emet-live: 8`** (real PMIDs: 21329690, 22136276, 26060906, 27226234, 27409709, 29338461,
  30069763, 38195686), `fda-primary: 3`, `corpus: 2`, `semantic-web: 39`, + real
  gnomad/gtex/interpro/gprofiler quantitative seams.
- **Two distinct planes:** internal (moat, `plane=internal`) vs external (EMET/public, `plane=external`).
- **The spread (real, no consensus):** Denali CSO `conditional·4`, BioMarin BD `conditional·3`,
  Takeda ex-FDA `conditional·3`, Third Rock GP `hold·0`, Adversarial Red-Team `hold·0`.
- **3 real DIVERGENCEs** (emerged naturally, not fabricated): NurOwn ALS CRL precedent; **AZD2014 in
  TSC1/2 gastric cancer (NCT03082833) Phase II terminated for lack of efficacy** — with an honest
  "oncology context, CNS relevance unclear" note; FAERS not accessed (honest gap).
- **Synthesis:** *Conditional advance · medium confidence*.

## Replay (the $0 front end)
- `frontend/bridge.py::replay(scenario)` loads the frozen capture (no model/network), stamps
  `_via="replay"`; `available_replays()` lists captures. On a missing file → honest error envelope.
- `frontend/main.py` gains a **"Replay (captured TSC2 · $0)"** chat profile → renders the captured run
  through the same render pipeline as a live run (provenance/tier/plane/flags **verbatim**).
- `frontend/DEMO_TSC2.md` — the 2-minute demo script.

## Data boundary / honesty
- The scenario is **tagged `_internal_only` + `_data_notice`** (it contains real internal Quiver moat
  data, `plane=internal`) — approved for the **internal** demo, not external distribution. EMET facts
  are real public PMIDs (external plane).
- Nothing is fabricated: real moat, real PMIDs, the real spread, real divergences. Replay only avoids
  re-paying the live cost; it does not alter the data.

## Gates
- **Gate 1:** `bash dev/run-tests.sh` → GREEN (frontend +7 replay tests; offline, $0, no live calls).
- **Gate 3:** scenario tagged internal-only; EMET = external plane, public PMIDs; 89 KB JSON (text,
  not a binary). No secrets.
- **Gate 4:** engine untouched (capture/replay are build-tool + frontend; `bridge.replay` stdlib `json`).
- **Gate 5:** `bridge.replay("tsc2_live_run")` conforms to the contract, carries the real PMIDs +
  moat + spread + DIVERGENCE; missing-scenario degrades honestly.

## Files
- `_build/capture_tsc2_live.py` (capture script) · `sapphire-orchestrator/scenarios/tsc2_live_run.json`
  (frozen real run, internal-only) · `frontend/bridge.py` (+replay) · `frontend/main.py` (+profile) ·
  `frontend/tests/test_replay.py` (+7) · `frontend/DEMO_TSC2.md`.
