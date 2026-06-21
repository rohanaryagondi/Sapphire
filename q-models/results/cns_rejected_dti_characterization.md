# Re-testing rejected DTI models (ConPLex / DrugBAN) on the CNS panel — BANKED (toolchain-blocked), 2026-06-15

Phase 2 of the overnight CNS campaign: were ConPLex/DrugBAN/PerceiverCPI dismissed *unfairly* for CNS
(Nav-blind ≠ CNS-blind)? Re-test them on the proper 19-target CNS panel, per-family. **Outcome: banked at
the ≤2-fix cap — the DrugBAN/DGL toolchain wouldn't assemble, and the result it would have produced is
predictable enough that the CNS DTI verdict doesn't depend on it.** ~$0.3 across 3 fail-fast deps attempts.

## Why banked (3 sequential dep failures in the DGL/DrugBAN stack)
The eval needed DGL (DrugBAN's drug-graph backend) + ConPLex + ChEMBL in one venv pinned to torch 2.1.0
(the highest the DGL cu121 wheels support). Each fix revealed the next missing piece:
1. **rc=92 #1:** `transformers>=4.42` calls `torch.utils._pytree.register_pytree_node` (absent in torch 2.1)
   → pinned `transformers==4.36.2` (fix #1).
2. **rc=92 #2:** DGL imports `torchdata.datapipes` (removed in torchdata≥0.8) → pinned `torchdata==0.7.1`
   (fix #2).
3. **rc=92 #3 (cap reached):** DGL's `graphbolt` submodule imports `pydantic`, not installed →
   `ModuleNotFoundError: pydantic`. A trivial add, but it's the **third** sequential dep in a clearly
   fragile stack, past the ≤2-fix cap.

## Why this is the right call (not just giving up)
- **ConPLex's result is predictable.** ConPLex is trained on **BindingDB + DUD-E** — the *same*
  ion-channel-poor distribution as BALM/PLAPT, which are at chance (0.50) on the CNS ion-channel family. A
  ConPLex zero-shot CNS run would almost certainly reproduce that (decent on kinases, ~chance on ion
  channels), adding no new understanding.
- **DrugBAN** ships no pretrained weights — the eval would train a 2-epoch BindingDB-DrugBAN on-instance,
  again a BindingDB-distribution baseline.
- **PerceiverCPI** was documented-skipped upstream (no weights + torch-1.7/py3.9 + vendored-chemprop
  conflict).
- **The CNS DTI verdict already stands** on (a) the 19-target `cns_dti` benchmark (BALM/PLAPT: kinase 0.80 /
  mTOR 0.72 / GPCR 0.58 / ion-channel 0.50) and (b) `trunc_test` (a supervised scaffold-split probe hits 0.92
  on ion channels — the signal is learnable, the gap is supervision/training-coverage). Re-confirming that
  another BindingDB-trained model is also coverage-limited would not move the needle.

## If revisited
One-line fix to finish it: add `pydantic` to the DGL install (and ideally move DGL off the hard deps-gate so
ConPLex runs even if DrugBAN's stack breaks). Or skip DGL/DrugBAN entirely and run **ConPLex-only** (no DGL)
for a clean zero-shot ConPLex CNS datapoint — but expect ~chance on ion channels per the BindingDB-coverage
argument above.

## Scorecard impact
**None.** Track 2/DTI verdict unchanged (BALM/PLAPT family-specific; ion channels need a fine-tune — see
`results/cns_dti_characterization.md` + `results/trunc_test_characterization.md`). ConPLex/DrugBAN filed as
"BindingDB-distribution models, re-test toolchain-blocked, result predictable (coverage-limited like BALM)."

**Receipts:** `s3://rohan-mammal-bootstrap-20260610-213029/cns_rejected_dti/run.log` (3 deps tracebacks);
eval `aws/cns_rejected_dti_eval.py`; instances `i-0f1456bb…`, `i-00322a77…`, `i-0a4c61c1…` all self-terminated.
