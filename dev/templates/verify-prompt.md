# Verify Prompt — functional verification (Gate 5) ⭐

*Dispatch a `sapphire-dev-verifier` (sonnet; opus for critical paths) with this. Independent of the implementer. This gate proves the change ACTUALLY WORKS — not that its (possibly vacuous) tests pass.*

```
Functionally verify a change to Sapphire by RUNNING it the way it will actually be used, then trying to break it. Repo: <path> (branch Rohan). You MAY run commands and the real entry points; do not modify source to make it pass (you may write throwaway probes).

## The claim
<What the change is supposed to do, in observable terms — e.g. "run_live now produces real persona verdicts when they cite the dossier", "predict.py returns GBR tox scores for ASO sequences", "trace_view renders a real run".>

## Verify behavior, not just green tests
1. **Run the real entry point** with realistic input. Show the actual output.
   - e.g. `run_live(query, ctx=<offline mocks + real moat>)` and inspect the dossier/roundtable/trace; or `echo '[...]' | python tools/aso_tox/predict.py --json`; or `python trace_view.py <eid>`.
2. **Confirm the observable claim is true** — quote the output that proves it (the verdict has a real stance; the score is present; the trace shows the agents). If the claim is "0 → N", show N.
3. **Adversarially probe** — empty/garbage input; the negative path (a guardrail that should block; a backend that's down); the boundary case. Confirm it fails safe (abstains/empties/errors honestly), never crashes or fabricates.
4. **Cross-check against the tests** — does any test pass *vacuously* (would still pass if the behavior were broken)? Name it.

## Output
### Verdict — Works as claimed | Does NOT work / partial
### Evidence — the commands you ran + the actual output proving (or disproving) the claim
### Breakage found — anything that crashed, faked, or misbehaved (with repro)
### Vacuous tests — any test that would pass on broken behavior
### Required fixes — concrete, if the verdict isn't "Works"
Begin with the verdict. Show real output, not assertions about it.
```
