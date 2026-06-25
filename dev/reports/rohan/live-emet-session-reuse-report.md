# live-emet-session-reuse — in-session EMET orchestration (KEYSTONE) — report

**Branch:** `rohan/live-emet-session-reuse` · **Built-By:** rohan · **Tier:** Feature

## Goal
Make the EMET evidence in a `run_live` engagement come from the user's **already-authenticated
BenchSci session** — not a fresh isolated browser — so a real run lands **real cited PMIDs**, while
keeping the honest-abstain path when no session exists. (Head Claude's resolved HELP decision:
**mechanism (c) — in-session orchestration**, the same way the `/sapphire` skill runs EMET; durable
answer is the future EMET-MCP.)

## Mechanism
The detached `claude -p` EMET runner spawns its own Playwright browser (can't inherit the logged-in
tabs; fights the Chrome profile lock) → it honestly abstains on the login screen. This change adds the
**in-session path**:

1. The **orchestrator drives EMET inside its own authenticated session** (the browser the user logged
   into) per the `emet-runner` skill — public identifiers only — and captures one EMET envelope per
   candidate.
2. That envelope is injected into `run_live` through the **existing `make_emet_handler(runner=…)`
   seam**, wrapped by the new **`emet/session_bridge.py::make_session_emet_handler(envelopes)`**
   (candidate-keyed, case-tolerant). `run_live` only wires its default abstaining handler when the
   caller didn't supply one (`_wire_emet_handler` = setdefault), so the session handler wins.
3. `run_live`'s `emet-runner` agent consumes the **real session evidence** → real PMIDs land as
   `emet-live` facts on the **external plane**.

No subprocess, no profile-lock fight, **no fabrication**: a candidate with no captured envelope →
honest abstain (`login_required` → escalate). The session stays **in-process** (no authenticated
profile written to disk — the credential-at-rest concern of the `--user-data-dir` fallback doesn't
apply).

## ⭐ Acceptance (THE evaluation — proven on a live run)
Drove EMET live in the authenticated session (Thorough / Target-Validation) for **TSC2 in tuberous
sclerosis** — chat `https://emet.benchsci.com/chat/5a13d6f6-5aa9-49bb-9d8d-0b19b1cda39f`, 17 sources,
citation-verification pass — captured the real envelope, injected it, and ran:

```
run_live("Is TSC2 a viable target in tuberous sclerosis?", ctx={emet_handler: session_bridge(...)})
→ emet-runner status : ok            (NOT abstained)
→ emet-live facts     : 8
→ real PMIDs in dossier: PMID:21329690, PMID:22136276, PMID:26060906, PMID:27226234,
                         PMID:27409709, PMID:29338461, PMID:30069763, PMID:38195686
→ plane (all external): True
```

These are **real PubMed IDs from the live EMET research** (TSC1/TSC2 GAP→Rheb→mTORC1 mechanism;
EXIST-1/2/3 phase III everolimus trials in SEGA / renal AML / epilepsy). **≥1 real emet-live PMID
landed in the dossier, not an abstain** — the fixed acceptance test passes.

## Gates
- **Gate 1:** `bash dev/run-tests.sh` → **495 GREEN** (emet **26**, +5 session-bridge tests). Offline,
  no live browser in CI. *(Note: the `tests` suite has a pre-existing load-sensitive flake — it fails
  only under heavy concurrent CPU load, e.g. while EMET research + live claude calls run; green when
  idle. Not introduced here.)*
- **Gate 3:** EMET = external plane, public identifiers only; PMIDs are real/verifiable; honest abstain
  on no-session. No secrets/binaries.
- **Gate 4:** engine stdlib-only — `session_bridge` imports only the first-party `emet.handler` seam.
- **Gate 5:** the live acceptance above (real PMIDs land via `run_live`); offline tests prove the
  injected handler lands facts and an uncovered candidate abstains (never fabricates).

## Files
- `sapphire-orchestrator/emet/session_bridge.py` (new — the in-session injection seam)
- `sapphire-orchestrator/emet/tests/test_session_bridge.py` (new — 5 offline tests incl. run_live)

## Honesty / boundary notes
- The captured claims + PMIDs are transcribed **faithfully** from the live EMET output (not invented).
- For the durable path, EMET-MCP remains the target (parked); this in-session path is the live-demo
  interim Head Claude approved. The shared `--user-data-dir` profile stays the documented fallback if
  in-session is ever unavailable (with the credential-at-rest caveat for Rohan/Quiver).
