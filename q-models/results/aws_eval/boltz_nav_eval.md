# Boltz-2 on Quiver's Nav (+ mTOR) targets — full evaluation report

**Run 2026-06-08 on the Yale Bouchet GPU cluster** (SLURM, account `pi_mg269`; NOT AWS — Rohan
ruled out AWS this session). Filed in `results/aws_eval/` alongside the prior PROTON + Boltz-partial
results. This is the evaluation the handoff package set up and the prior AWS run could not finish.

**The question:** does Boltz-2 — a structural co-folding + affinity model, architecturally unlike the
BindingDB-trained PLMs that failed before — separate Nav1.8 binders from decoys where MAMMAL (0.43)
and ConPLex (0.39) both sat at chance?

> **Status note (paused 2026-06-08 ~11:33).** Tests A–D are complete and the headline is locked.
> Three follow-ups are partial/pending and clearly marked below: Test E (cross-paralog, 36/99 done),
> the off-target control (UBE3A/TUBB **complete**; vixotrigine×Nav 2/9), and a positive control
> (CA2/CDK2, built but **not yet run** — blocked by GPU queue contention). Raw data files listed in §11.

---

## 1. Executive summary

| Test | Target | Result | Read |
|---|---|---|---|
| B (headline) | **Nav1.8** binder-vs-decoy | **AUROC 0.714** | clears 0.70 bar; **marginal** (n=28, p=0.16) |
| D | **mTOR** binder-vs-decoy | **AUROC 1.000** | **decisive** (p=0.029); MAMMAL failed this (0.56) |
| C | suzetrigine × 9 Nav paralogs | Nav1.8 ranked #1, but tiny margin | **weak** selectivity, low off-target Δ |
| E (partial) | per-paralog reproduction | Nav1.7 0.71, Nav1.5 0.75, Nav1.8 0.75 | signal **reproduces** across paralogs |
| off-target | Nav drugs × UBE3A / TUBB | binders > off-targets; decoys flat | **target-aware but soft** |

**Three things are simultaneously true, and together they are the finding:**

1. **Boltz-2 is genuinely good where there's structural precedent.** mTOR (a large, well-studied kinase
   with a canonical pocket and famous macrocyclic ligands) is a clean win — AUROC 1.000, statistically
   significant. This matches what Boltz-2 is built for (it approaches FEP accuracy on the FEP+/OpenFE
   kinase benchmark and won the CASP16 affinity challenge).

2. **On Nav1.8 it is materially better than the prior models, but only marginally good in absolute
   terms.** AUROC 0.714 is the first off-the-shelf result above chance (MAMMAL 0.43, ConPLex 0.39), the
   four highest-scored compounds are all true Nav1.8 binders, and the separation reproduces on Nav1.7
   (0.71) and Nav1.5 (0.75). But n is tiny (p=0.16, 95% CI ≈ [0.40, 1.00]), the absolute binder
   probabilities are all sub-0.5 even for true binders, and paralog selectivity is weak.

3. **Its scores are target-conditioned, not pure drug-bias — but the specificity is soft.** Against two
   unrelated proteins (UBE3A, an E3 ligase; TUBB, tubulin), every Nav binder scored *higher* on Nav1.8
   than on either off-target, while decoys showed no preference. That's real target-awareness, and a
   clear step up from MAMMAL (whose predictions compressed everything to a "moderate binder" band). But
   the margins are modest, and one lipophilic compound (A-803467) keeps a ~0.46 "binder" probability
   even on proteins it cannot bind.

**Bottom line for Quiver.** Off-the-shelf Boltz-2 is a usable tool on well-precedented targets (mTOR/
kinases) and a real improvement over MAMMAL/ConPLex on Nav — useful as a **coarse "is this a
Nav-blocker-like molecule" pre-filter**. It is **not** a confident Nav binder-triage oracle: low-
confidence probabilities, soft paralog discrimination, and it does not deprioritize the Nav1.5 cardiac
off-target. **For reliable Nav1.8-vs-Nav1.5 selective triage, the in-house Quiver Nav fine-tune remains
the path.**

---

## 2. Methods

- **Hardware:** Bouchet `gpu` partition (RTX 5000 Ada 32 GB) for small targets; `gpu_devel` (H200
  141 GB) for the 1791–2549 aa channel/mTOR targets. Driver 570.195. Boltz 2.2.1, torch 2.11.0+cu128.
- **Readout:** Boltz-2 affinity head `affinity_probability_binary` ∈ [0,1] (reported as `prob_binder`),
  plus `affinity_pred_value` (predicted log₁₀ IC₅₀). Structure sampling `--sampling_steps 100
  --diffusion_samples 1`; affinity sampling at defaults except Test E (see §7).
- **`--no_kernels`** (pure-PyTorch reference path) — required here; see §10 for why.
- **MSA:** ColabFold hosted MMseqs2 server (`--use_msa_server`); GPU nodes have outbound internet.
- **Scoring:** Mann-Whitney AUROC (`score_results.py`); exact one-sided p-values and Hanley-McNeil
  CIs computed separately given the small n.

---

## 3. Test A — install sanity (PASSED)

4 GPCR×decoy pairs (ADRB2, DRD2; 413–443 aa), RTX 5000 Ada, ~90 s each, 4/4 rc=0. Decoy probs all
≤ 0.52 (ADRB2/lidocaine 0.48, ibuprofen 0.08, DRD2/metformin 0.52, caffeine 0.05). Pipeline validated
end-to-end (weights → MSA → GPU → `--no_kernels` → affinity parse) before spending H200 time.

## 4. Test B — Nav1.8 binder-vs-decoy (THE HEADLINE)

Nav1.8 (SCN10A, 1956 aa) × 7 Nav blockers + 4 decoys, on one H200, 11/11 rc=0, ~7 min each.

| prob_binder | class | compound |
|---:|---|---|
| 0.598 | **BINDER** | A-803467 (potent selective Nav1.8 blocker) |
| 0.483 | **BINDER** | mexiletine |
| 0.468 | **BINDER** | suzetrigine (Quiver's lead, VX-548) |
| 0.286 | **BINDER** | ranolazine |
| 0.252 | decoy | ibuprofen |
| 0.188 | decoy | caffeine |
| 0.173 | BINDER | carbamazepine |
| 0.126 | BINDER | lidocaine |
| 0.103 | decoy | metformin |
| 0.053 | decoy | atenolol |
| 0.048 | BINDER | lacosamide |

**AUROC = 0.714** (mean_pos 0.312, mean_neg 0.149, sep +0.162). Exact one-sided Mann-Whitney
**p = 0.158**; Hanley-McNeil 95% CI ≈ **[0.40, 1.00]**; leave-one-out range 0.67–0.83. The four highest
scores are all true binders; the misses (lacosamide, lidocaine, carbamazepine) are the weak/promiscuous
older blockers — a chemically defensible ordering, though the label set counts them as equal positives.
**Clears the bar and crushes MAMMAL/ConPLex, but is not statistically robust on this test alone** —
which is why C/D/E and the off-target control matter.

## 5. Test C — suzetrigine pan-Nav selectivity (9/9)

suzetrigine × all 9 paralogs. Boltz ranks **Nav1.8 #1 (0.440)** — correct, since suzetrigine is
Nav1.8-selective. But: margin over Nav1.6 (0.419) is only +0.021; the whole spread is a narrow
0.31–0.44; Nav1.5 (cardiac off-target) is mid-pack (0.391), not down-weighted; and the absolute prob on
the true target is sub-0.5. **Correct rank-1, low off-target Δ — a soft signal.**

Ranked: Nav1.8 0.440 > Nav1.6 0.419 > Nav1.7 0.418 > Nav1.4 0.412 > Nav1.1 0.404 > Nav1.5 0.391 >
Nav1.2 0.378 > Nav1.3 0.346 > Nav1.9 0.310.

## 6. Test D — mTOR triage (7/7) — the clear win

mTOR (2549 aa) × 3 rapalogs + 4 decoys. Perfect separation:

| compound | prob | class |
|---|---:|---|
| sirolimus | 0.661 | rapalog |
| everolimus | 0.598 | rapalog |
| temsirolimus | 0.537 | rapalog |
| caffeine | 0.309 | decoy |
| metformin | 0.233 | decoy |
| ibuprofen | 0.095 | decoy |
| atenolol | 0.057 | decoy |

**AUROC = 1.000** (sep +0.425, exact **p = 0.029 — significant**). MAMMAL failed mTOR (matched-decoy
0.56, off-target Δ −1.12). Strongest result of the run, on co-folding's home turf.

## 7. Test E — cross-paralog reproduction (partial, 36/99)

Full 9-paralog × 11-drug panel, reordered paralog-major, structure sampling as B/C/D but reduced
affinity sampling (1×100 vs 5×200) to fit the wall. Stopped at 36/99 at Rohan's request (the point was
made). Completed paralogs:

| paralog | AUROC (Test E, reduced affinity) |
|---|---:|
| Nav1.8 | 0.750  (cf. Test B full-affinity 0.714 — consistent) |
| Nav1.7 | 0.714 |
| Nav1.5 | 0.750 |

**The Nav1.8 separation reproduces across paralogs (all 0.71–0.75)** — it is not a one-off, and the
reduced-affinity config matches the full-affinity headline, validating the speed-up. Nav1.6 was at
4/11 when stopped; Nav1.1–1.4, 1.9 not reached.

## 8. Off-target control — target-aware or drug-only bias? (complete)

The decisive test for the drug-bias concern. The within-Nav-family Δ being small (Test C) isn't damning
on its own — paralogs are homologs. The sharp test: do the Nav drugs' scores **collapse** on proteins
they cannot bind? Scored each drug against **UBE3A** (E3 ubiquitin ligase, 875 aa) and **TUBB** (tubulin
β, 444 aa), replicating the repo's MAMMAL `offtarget_ube3a.py` design for a head-to-head.

| drug | Nav1.8 | UBE3A | TUBB | Δ(Nav−UBE3A) | Δ(Nav−TUBB) |
|---|---:|---:|---:|---:|---:|
| mexiletine (binder) | 0.483 | 0.092 | 0.087 | **+0.39** | **+0.40** |
| suzetrigine (binder) | 0.468 | 0.291 | 0.155 | +0.18 | +0.31 |
| vixotrigine (binder)\* | 0.318 | 0.149 | 0.163 | +0.17 | +0.16 |
| A-803467 (binder) | 0.598 | 0.466 | 0.465 | +0.13 | +0.13 |
| caffeine (decoy) | 0.188 | 0.226 | 0.247 | −0.04 | −0.06 |
| ibuprofen (decoy) | 0.252 | 0.280 | 0.189 | −0.03 | +0.06 |

\* vixotrigine Nav1.8 from the partial vixotrigine run (§9), full-affinity config.

**Read: target-aware but soft.**
- **Real target-awareness:** all 4 true binders score higher on Nav1.8 than on *either* unrelated
  protein (every Δ positive), and both decoys are flat (no Nav preference). Boltz's scores are
  conditioned on the target, not purely intrinsic to the molecule. This is a clear step up from MAMMAL,
  whose pKd predictions compressed everything to ~6–7 (suzetrigine: Nav1.8 7.00 vs UBE3A 6.48, Δ +0.53
  on a saturated scale).
- **But soft, and leaky on one compound:** the discrimination is modest (mean binder Nav−off ≈ +0.2),
  and **A-803467 keeps a ~0.46 "binder" probability on both off-targets** — a high false-positive for
  proteins it has no business binding. mexiletine is the cleanest (0.48 → ~0.09).

## 9. vixotrigine (partial)

vixotrigine (BIIB074/raxatrigine, CID 16046068) was added at Rohan's request. Off-target scores are in
(§8). Its Nav profile is partial (2/9 before the pause): **Nav1.8 0.318, Nav1.7 0.384** — low absolute
scores on its own targets, echoing suzetrigine (Boltz does not confidently call either Nav-selective
drug a binder). Remaining 7 paralogs pending (panel staged: `vixotrigine_nav_panel.json`).

## 10. Pending: positive control (NOT yet run)

A sanity check — does Boltz cleanly separate binders from decoys on targets it's *known* good at, using
the **identical decoys** as the Nav test? Built but not yet run (blocked by Ada queue contention, then
paused): **CA2** (carbonic anhydrase II, 260 aa; sulfonamide drugs acetazolamide/methazolamide/
dorzolamide/brinzolamide) and **CDK2** (298 aa, an FEP+ kinase; dinaciclib/roscovitine/AT7519), each ×
{caffeine, metformin, ibuprofen, atenolol}. Panel staged: `poscontrol_panel.json`. Expected: AUROC ≈
1.0; if so, it confirms the pipeline is sound and Nav is genuinely the hard case (not a setup artifact).
**This is the most valuable remaining run.**

---

## 11. The corrected install (supersedes the handoff recipe)

Four corrections — two of them are exactly what silently broke the prior AWS run:

1. **Wrong kernel package name.** Handoff says `cuequivariance-ops-cu13-torch`; that does not exist.
   Boltz 2.2.1's real `[cuda]` extra is `cuequivariance_ops_torch_cu12` + `cuequivariance_ops_cu12`
   (suffix `-torch-cu12`, **cu12 only — no cu13**).
2. **The handoff's verify line is a false positive.** `from cuequivariance_torch.primitives.triangle
   import triangle_multiplicative_update` prints OK with *no* kernels installed (lazy import). The real
   check is `import cuequivariance_ops_torch`. The prior AWS "fix" was never actually verified.
3. **PyPI's default torch is now 2.12+cu130 (CUDA 13), which driver 570 cannot run**
   (`torch.cuda.is_available()` → False even though nvidia-smi sees the GPU; CUDA 13 needs driver ≥580).
   Pin a cu128 torch: `pip install torch --index-url https://download.pytorch.org/whl/cu128`.
4. **The cu12 kernels still crash at runtime here** (`libcue_ops.so` / ABI; a direct kernel smoke test
   failed rc=1 even on a 413 aa protein). So run with **`--no_kernels`** (pure-PyTorch reference path;
   kernels are only a speed/memory optimization). Cost: ~2000 aa proteins OOM the 32 GB Ada, so
   channel/mTOR targets run on the H200.

Also: handoff gotcha #3 ("`--sampling_steps_affinity` doesn't exist") is **stale for 2.2.1** — those
flags exist and were used in Test E.

## 12. Files & reproduce

Raw results in this directory:
- `boltz_nav1.8_results.json` — Test B (11 Nav1.8 complexes)
- `boltz_mtor_results.json` — Test D (mTOR, AUROC 1.000)
- `boltz_suzetrigine_selectivity_results.json` — Test C (suzetrigine × 9 paralogs)
- `boltz_navfull_partial_results.json` — Test E (36/99 partial; Nav1.7/1.5/1.8 complete)
- `boltz_offtarget_vixotrigine_results.json` — off-target panel (UBE3A/TUBB × 6 drugs) + vixotrigine×Nav (2/9)

Environment (venv, cached weights, sbatch scripts, the `--no_kernels` runner, staged panels) lives on
Bouchet scratch at `…/Sapphire/boltz_run/` (gitignored — 7.5 GB weights + venv). Score with the
handoff's `score_results.py`.

To resume: run `vixotrigine_nav_panel.json` (remaining paralogs) and `poscontrol_panel.json` on the
H200 (`gpu_devel`), then append §9/§10 results and the positive-control verdict here.
