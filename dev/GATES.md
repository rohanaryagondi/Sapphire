# Gates — Definition of Done

Nothing lands on `Rohan` until it passes these. They are listed in the order you run them. A "Feature"-tier change runs all of them; a "Standard"-tier change runs 1–5; a "Trivial"-tier change runs 1 (+ common sense). See tiers in [`METHODOLOGY.md`](METHODOLOGY.md).

A change is **Done** when every applicable gate is green **and** the [ledger](LEDGER.md) records it.

---

## Gate 1 — Full test surface green
The entire suite passes. No merge on red, no skipped-as-hidden-failure.
```
cd sapphire-orchestrator && for s in contracts harness emet memory selfimprove moat tests; do python -m unittest discover -s $s/tests; done
```
Warnings in test output are findings, not noise — investigate them.

## Gate 2 — Independent subagent review (spec + quality)
A `sapphire-dev-reviewer` (NOT the implementer) reads the change's diff and returns a verdict: spec compliance (nothing missing/extra/misunderstood vs. the brief) + code quality (clean, real tests, edge cases). **Approved** is required. Important/Critical findings go back to a fix loop and are re-reviewed. Template: [`templates/review-prompt.md`](templates/review-prompt.md).

## Gate 3 — Provenance + secret/binary scan
- No secrets committed: `git diff` carries no `.env`/keys/tokens/passwords.
- No large/unexpected binaries added; gitignores intact (`RohanOnly/moat/`).
- Every new fact-emitting path uses an **allowed** provenance label from `contracts/provenance.py`; no unlisted labels.
- Public-identifiers-only boundary respected.

## Gate 4 — Stdlib-runtime + verbatim-vendor check
- The engine gained no third-party import: grep the runtime (`live_engine.py`, `harness/`, `moat/`, `orchestrator.py`, seams) — only stdlib + first-party. Third-party deps stay in `_build/` or tool subprocesses.
- If vendored/proprietary logic was integrated, it is **character-for-character identical** to the source, locked by a golden-value test, with the original artifact preserved and the dependency version pinned.

## Gate 5 — Functional verification ("does it actually work?")  ⭐
**This is the gate that "tests pass" cannot replace.** A `sapphire-dev-verifier` (independent) **actually runs the change** the way it will be used, tries to break it, and confirms it does what it claims — end-to-end, not just unit-mocked:
- Run the real entry point (e.g. `run_live` with a real moat read; `predict.py` on real sequences; `trace_view` on a real trace).
- Adversarially probe: empty/garbage input, the negative path, the boundary case, the "what if the backend is down" path.
- Confirm the *observable behavior* matches the claim (the roundtable actually produces verdicts; the tool actually returns scores; the guardrail actually blocks).
- **Any gap between "claimed" and "actually does" → back to the fix loop, then re-verify.**

Template: [`templates/verify-prompt.md`](templates/verify-prompt.md). This gate exists because a green suite once hid a wiring bug that made the entire roundtable a no-op — the unit test asserted on the broken output. Verifiers catch what mocks miss.

## Gate 6 (Feature tier) — Whole-branch review
Before a feature ships, an **opus** integrator/reviewer reads the full commit range and judges it as one coherent change: architecture fit, cross-cutting risk, that the parts compose. Verdict **Ready to merge**.

---

## The merge checklist (paste into the ledger entry)
```
[ ] Gate 1  full suite green        (N tests)
[ ] Gate 2  independent review      Approved
[ ] Gate 3  provenance + no secrets/binaries
[ ] Gate 4  stdlib runtime + verbatim vendor (if applicable)
[ ] Gate 5  functional verification — RAN it, adversarial, behaves as claimed
[ ] Gate 6  whole-branch review     Ready to merge   (feature tier only)
[ ] Ledger updated · conventional commit · pushed origin/Rohan
```
