# Sapphire — Overall Status

*One screen: where the build is. Updated 2026-06-22. Detail in the per-area docs; assignments in
[`WORKBOARD.md`](WORKBOARD.md).*

## Headline
The two-bucket firm runs end-to-end. Phases 1–6 are done. **278 tests green.** Fact sources are largely
**live/real** (EMET, personas, Q-Models, internal moat, ASO-tox); the keystone remaining is wiring the live
harnessed path (`run_live`) to the front door.

## At a glance
| Area | State | Live vs mock | Detail |
|---|---|---|---|
| Engine (orchestrator + live_engine) | ✅ runs end-to-end | canned path live; `run_live` verified offline, **not yet at front door** | [engine.md](engine.md) |
| Runtime harness (22 agents) | ✅ done | guard-enforced, provenance-stamped, traced | [runtime-harness.md](runtime-harness.md) |
| Fact tools | ✅ mostly real | EMET live · personas live · Q-Models real · moat **real** · ASO-tox **real** | [tools.md](tools.md) |
| Dev/build harness | ✅ done | 3-contributor, PR-gated, local enforcement | [dev-harness.md](dev-harness.md) |
| Front door (serve.py / Console) | ⚠️ canned path only | uses pre-captured scenarios, not `run_live` | [engine.md](engine.md) |

## Phases (done)
- **P1–P3:** control agents + Bucket-1 fact agents + Bucket-2 partners; orchestrator runs end-to-end (triage→
  plan→dossier→roundtable→synthesis); Console front face.
- **P4:** Q-Models toolset vendored; orchestrator can call any tool; two-speed routing (local-cpu sync /
  gpu-launch async); live AWS plumbing proven.
- **P5:** agent harness + live EMET + self-improvement loop + scenario suite.
- **P6:** ASO-tox tool integrated; **`run_live(..., sequences=...)`** feeds it real GBR tox facts (shipped
  2026-06-22, PR-gated).

## Top open items (→ flow to the workboard when assigned)
1. **Wire `run_live` to the front door** — replace the canned path in `serve.py`/Console with the live
   harnessed firm. *The keystone.* (engine.md)
2. **ASO Design tool** — build it; feed its designed sequences into the `aso-tox` `sequences=` channel. (tools.md)
3. **Broaden captured scenario coverage** across the 10-axis variety matrix. (engine.md)
4. **Retire remaining mocks honestly** / mark every track's provenance. (tools.md)
5. **Chronic-tox model** integration (roadmap). (tools.md)
6. **Quantitative-fact seams** (assigned `quant-fact-seams`, **hayes**) — gnomAD constraint, GTEx, InterPro,
   g:Profiler as Bucket-1 seams: hard numbers alongside EMET's narrative. Pilot-gate (gnomAD first). (tools.md)

## Top risks
- **Enforcement is local-only** (free repo, no branch protection/Actions) — relies on cooperating agents +
  `dev/audit-history.sh`. See `dev/CONVENTIONS.md` §1.
- **Front-door still canned** — demos don't yet exercise the live path; don't overclaim "live" for the Console.
- **Mock surfaces** must stay labeled; "SOTA on shit is still shit."
