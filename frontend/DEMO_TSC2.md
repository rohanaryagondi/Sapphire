# Demo script — TSC2 / tuberous sclerosis (the real run, replayable $0)

A 2-minute walkthrough of the Sapphire firm on a real CNS target question, replaying a **frozen
real engagement** (real Quiver moat + real EMET PMIDs + the live persona spread + real DIVERGENCEs)
with **no model and no network** — instant, deterministic, $0.

## Run it
```bash
pip install -r frontend/requirements.txt
cd frontend && chainlit run main.py        # http://localhost:8000
```
Pick the **"Replay (captured TSC2 · $0)"** chat profile, type anything (e.g. *"Is TSC2 a viable
target in tuberous sclerosis?"*), and the captured run renders instantly.

> For a genuinely live run instead, pick **"Live (cheap · haiku)"** (needs the `claude` CLI + a
> logged-in EMET session). The replay was captured that way via `_build/capture_tsc2_live.py`.

## What to point at (the story)
1. **Plan** — the firm scopes TSC2 in tuberous sclerosis / mTORopathy.
2. **Two data planes, distinct:**
   - **Internal plane (Quiver moat, real):** EP-signature neighbors of *TSC2 KO* — e.g. *TSC1 ~ TSC2 KO
     (cos 0.083)* — Quiver's private CNS_DFP signal. *(Internal-demo only; tagged `_internal_only`.)*
   - **External plane (real EMET PMIDs):** TSC1/TSC2→Rheb→mTORC1 mechanism (PMID:21329690), and the
     **EXIST-1/2/3** phase III everolimus trials (PMID:22136276 SEGA, PMID:27409709 renal AML,
     PMID:29338461 epilepsy) — captured live from BenchSci EMET, **real PMIDs, not fabricated**.
3. **The spread (no forced consensus):** the real spread is the **3 conditional verdicts** — Denali
   CSO *conditional·4*, BioMarin BD *conditional·3*, Takeda ex-FDA *conditional·3*. The Third Rock GP
   and the Adversarial Red-Team **abstained on the harness guardrail check** (`status: abstained`,
   guardrail-violation — rendered as *hold·0*); that's the guard working — it refuses an ungrounded
   verdict — **not** a deliberate "no." Present those two as **abstentions, not holds.**
4. **DIVERGENCE (surfaced, not reconciled):** the headline, CNS-relevant one is **AZD2014 in TSC1/2
   gastric cancer (NCT03082833) Phase II *terminated for lack of efficacy*** — flagged with an honest
   note that it's an oncology context whose CNS relevance is unclear. *(Two other DIVERGENCE entries
   in the capture are lower-signal — a NurOwn/ALS corpus-bleed precedent and a "FAERS not accessed"
   gap; lead with the AZD2014 one.)* This is the "what the room sees that the headline misses" moment.
5. **Synthesis:** *Conditional advance · medium confidence* — the facts + how each player reacted,
   not a single verdict.

## Honesty notes
- Every fact carries its **tier · provenance · plane** verbatim; the EMET PMIDs are real and
  verifiable; the moat values are real internal Quiver data (tagged internal-only).
- The capture is a real `run_live` (contract-validated). Replaying it changes nothing about the
  data — it just avoids re-paying the live model/network cost.
