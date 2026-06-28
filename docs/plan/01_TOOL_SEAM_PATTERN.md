# 01 — The tool-seam pattern (how any Quiver tool plugs into the firm)

> The goal: a new tool is a **registry entry + an adapter**, never a new bespoke code path. This pattern
> generalizes the existing `aso-tox` seam + the Q-Models async launcher so the same contract covers a
> stdlib function, a sklearn subprocess, a Docker container, and a multi-hour AWS pipeline.

## 1. What a "seam" is
A seam is the thin, contract-bound boundary between **the engine** (stdlib-only, deterministic, runs the
firm) and **a tool** (which may need R, Docker, GPUs, big reference data, the network). The engine never
imports the tool's heavy deps; it calls the seam, which dispatches to the tool in the right environment and
returns a **validated, provenance-stamped envelope**.

```
  engine (stdlib)  ──calls──▶  seam adapter  ──dispatches──▶  tool (its own env)
        ▲                          │                              │
        └──── validated envelope ◀─┘  (schema + provenance + trace)
```

Reference implementations to copy:
- `sapphire-orchestrator/tools/aso_tox_seam.py` — kind `python`; stdlib seam → sklearn subprocess. The model.
- `sapphire-orchestrator/qmodels/` — the async AWS launcher (tagged EC2 → run `*_eval.py` → retrieve → teardown → ledger). The model for anything GPU/long-running.
- `sapphire-orchestrator/harness/` — the runtime every seam call goes through.

## 2. The five-part contract (every tool fills these in)

**(a) Registry entry** — in `sapphire-orchestrator/harness/agents.json`:
```
{ "id": "<tool-id>", "kind": "<exec-tier>", "class": "evidence|design|experiment",
  "provenance": "<stamp>", "activates_when": "<predicate>", "schema": "<output schema id>" }
```

**(b) Input contract — the data boundary (non-negotiable).** Only **public identifiers** cross the seam:
gene symbols, SMILES, disease terms, transcript accessions, **sequences**, ordinal ranks. **Never** Quiver
internal scores, EP/CRISPR traces, candidate IDs (`QS…`), or `CNS_DFP` cosine distances. The harness
`data_boundary` guardrail enforces this mechanically — a violation → `abstained / guardrail-violation`,
never a leak.

**(c) Execution tier** — pick the lightest that works:
| Tier | Use when | Mechanism | Example |
|---|---|---|---|
| `inline-stdlib` | pure-python, fast, no heavy deps | called in-process | small scorers |
| `python-subprocess` | needs a pinned dep (sklearn, numpy) | subprocess + JSON I/O; dep isolated | `aso-tox` |
| `container` | needs a packaged scientific tool | Docker image, mounted dir | OligoWalk (RNAstructure) |
| `aws-async` | GPU / hours / big reference data | tagged EC2 → run → retrieve → teardown → ledger | ASO off-target; Q-Models GPU |
The engine stays stdlib-only regardless of tier; heavy deps live *only* in the tool's environment.

**(d) Output contract — the envelope.** The seam returns a schema-valid object the harness validates +
stamps. Two shapes:
- **Evidence tools** → cited **facts**: `[{value, field, tier, provenance, source, plane, flag?}]` (the
  dossier shape). Each claim cited or dropped — never fabricated.
- **Design tools** → an **asset bundle** + facts about it: `{asset_type, candidates:[…], annotations:[…],
  provenance, run_ref}`, plus the per-candidate facts that re-enter Bucket 1 (e.g. tox, off-target).

**(e) Honest degradation.** If the tool can't run (no creds, no GPU, dep absent, login required), the seam
**abstains with a reason** and stamps it — never returns a fake/mock result silently. Mock/sim outputs, when
used, are labeled (`simulated`/`mock`) so provenance never lies. This is the "SOTA on shit is still shit"
rule applied to plumbing.

## 3. Where a tool fires (activation)
The Engagement Lead's plan decides activation from the ask's **capability class**:
- **evidence** tools fire in Bucket 1 on the relevant identifiers (e.g. `aso-tox` fires when ASO sequences
  are present).
- **design** tools fire when the engagement asks to *make* something, or when the synthesis concludes a
  target is worth pursuing → design the modality. Their assets loop back into Bucket 1.
- **experiment** tools fire at synthesis, consuming the open questions / DIVERGENCEs to propose the test.

## 4. The design-tool loop (what's new vs evidence tools)
Evidence tools are one-shot: identifier → facts. Design tools are a **loop**:
```
  target (validated) ─▶ DESIGN tool ─▶ candidate assets ─▶ assess each (evidence tools)
        ▲                                                          │
        └──────────────── refine / re-rank / re-design ◀──────────┘
```
The seam for a design tool therefore also declares: its **runtime budget** (minutes/hours), its **cost
ledger** hook (it spends AWS), and the **assess-step** that converts each asset into Bucket-1 facts.

## 5. Checklist to add a new tool
1. Write a one-page tool spec (inputs = public IDs, outputs, env, runtime, cost). Put it in `docs/plan/`.
2. Add the registry entry (`agents.json`) — id, kind/tier, class, provenance, activation predicate, schema.
3. Implement the seam adapter (`tools/<tool>_seam.py`) — stdlib on the engine side; heavy deps behind the tier.
4. Define/great-reuse the output schema in `contracts/`; ensure `data_boundary` covers its inputs.
5. Wire activation into the engagement plan (control) + the dispatch list (`live_engine`).
6. Add an honest-degradation path + a test that proves it abstains (doesn't fake) when the tool is absent.
7. For `aws-async`: reuse the Q-Models launcher (tagged resources, create-only + ledger, teardown-by-id).
8. Add a captured scenario so the canned path can demo it $0.

> Anti-pattern to avoid: a tool that reaches into the engine, bypasses the harness, or invents a new
> result-rendering path. If it doesn't go through the seam + harness, its provenance and data-boundary
> guarantees don't hold.
