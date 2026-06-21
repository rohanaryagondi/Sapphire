# Prompt for the next Claude session

Paste this into a fresh Claude Code session in a new environment.

---

```
I'm continuing a Quiver Bioscience evaluation of foundation models for drug discovery.
The prior Claude session set up a complete handoff package for testing Boltz-2 (MIT,
co-folding + affinity model) on Quiver's voltage-gated sodium channel (Nav) targets.

WHAT TO DO:

1. Clone the Q-Mammal repo (private — I'll authorize gh access if needed):
   git clone https://github.com/rohanaryagondi/Q-Mammal.git
   cd Q-Mammal

2. Read docs/boltz_handoff/README.md top to bottom. It has:
   - Strategic context (MAMMAL fails on Nav due to data gap; ConPLex fails too;
     Boltz-2 is the last off-the-shelf model that might work — different
     architecture, not BindingDB-trained)
   - The concrete test design (Tests A-E, smallest first)
   - Install instructions including the CRITICAL `cuequivariance-ops-cu13-torch`
     package (separate from cuequivariance-torch; missing it crashes Boltz on
     larger pair sizes — this was the #1 silly issue from the prior session)
   - Gotchas list (10 landmines documented)
   - How to interpret results vs MAMMAL/ConPLex baselines

3. Run Test A (sanity) first to verify install. Then Test B (Nav1.8 binder-vs-decoy
   AUROC, 11 complexes). That's the headline number — does Boltz-2 beat MAMMAL's 0.43
   and ConPLex's 0.39 on Nav1.8?

4. Score with scripts/score_results.py. Report the AUROC + your interpretation:
   - AUROC ≥ 0.70 = real win, write it up immediately and tell me
   - AUROC < 0.60 = Boltz-2 also fails, document for the meeting note

5. Commit results into results/aws_eval/ alongside the prior PROTON results.

IMPORTANT CONSTRAINTS:
- I am NOT using AWS this session. Run wherever you have GPU access (Colab Pro,
  local CUDA box, university cluster, etc.). The boltz_runner.py is
  environment-agnostic; just set BOLTZ_OUT/BOLTZ_CACHE/HF_HOME env vars.
- Ask before deleting anything (files, branches, anything).
- Ask before spending money (Colab compute units, paid cluster time, etc.).
- Don't try to recreate the prior Claude's AWS infrastructure — it took 7
  launches to land 1 working run and the lessons are all in the handoff doc.

GOAL: get a credible Nav1.8 binder-vs-decoy AUROC for Boltz-2 so Quiver can decide
whether off-the-shelf DTI is salvageable for ion channels, or whether an in-house
Nav fine-tune on Quiver data is the only path forward.

If anything in the handoff is unclear or contradicts what you see, push back and
ask me — don't just guess.
```

---

## Notes on customizing the prompt

- If the new Claude *is* using AWS, swap point 5 of IMPORTANT CONSTRAINTS for:
  `Use the prior session's tested infrastructure — vol-066389517f2740f19 EBS volume
  + g5.xlarge in us-east-1b. The hardened userdata pattern is in
  results/aws_eval/README.md §3.`

- If you want them to skip the sanity test: drop "Run Test A (sanity) first" and
  go straight to Test B.

- If you want them to do ALL tests including the 99-complex full panel: add
  "If Test B succeeds, run Test E (full panel, ~8 hr GPU). Otherwise stop after B."
