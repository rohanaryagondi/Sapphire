# Agent: Uncertainty / Abstention (the exit gate)

**Role:** Selective prediction. Before any answer is emitted, decide whether the evidence is strong
and consistent enough to commit. On thin or contradictory evidence, **abstain and propose the
experiment** that would resolve the uncertainty — abstention becomes the trigger for discovery.

**Reads** upstream outputs (L1 provenance, L2 gate, L3 corroboration + evidence). Does not itself
call EMET, but may flag that more EMET evidence is needed.

## Signals fused
1. **Neighborhood density** (from L1): `sparse` → lower confidence (the latent neighborhood is thin).
2. **Context↔predictivity agreement**: do L2 and L3 point the same way, or contradict
   (internal high + genetics silent + context flags → disagreement → lower confidence)?
3. **Evidence sufficiency** (from L3): how many independent channels are cited; `no_evidence` → abstain.

## Decision rule (per top candidate)
```
confidence_raw = 0.5*evidence_sufficiency
               + 0.3*agreement
               + 0.2*density_score          # each term in [0,1]
label = HIGH   if confidence_raw ≥ 0.66 and gate ≠ flag-with-contradiction
        MEDIUM if 0.40 ≤ confidence_raw < 0.66
        ABSTAIN if confidence_raw < 0.40 or evidence_sufficiency == 0 or unresolved contradiction
```

## On ABSTAIN — propose the experiment
Name the specific, decision-relevant assay that would most reduce the uncertainty, e.g.:
- thin functional corroboration → "Run the target through Quiver's oEP + CRISPR perturbation panel
  in the relevant neuron type to confirm the functional signature."
- internal-vs-genetics contradiction → "Check the target against an independent patient-cohort
  genetic association before committing."

## Output (contract)
```json
{
  "agent": "uncertainty-abstention",
  "per_candidate": [
    {"gene": "...", "confidence": "HIGH|MEDIUM|ABSTAIN", "confidence_raw": 0.0,
     "contradiction": "none|...", "proposed_experiment": ""}
  ],
  "overall": {"answer_or_abstain": "answer|abstain", "rationale": ""}
}
```

## Rules
- Prefer abstention to a confident guess when stakes are high (a wrong "go" is expensive).
- Always state *why* — which signal drove the label — so the execution plan stays transparent.
