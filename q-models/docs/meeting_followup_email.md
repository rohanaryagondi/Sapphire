# Follow-up on the 6/5 MAMMAL check-in

**To:** Matt, Graham, Mahdi, David
**From:** Rohan
**Date:** 2026-06-07

Hi all — brief answers to what came up Wednesday. Full detail in
`docs/meeting_followup_report.md` and the slide deck in
`Presentations/June7Followup/`. Both on the
[Q-Mammal repo](https://github.com/rohanaryagondi/Q-Mammal).

---

### Q1 — Is the Nav binding failure a *data gap* or a *model limit*? *(Graham, Matt)*

**Both.** The dataset MAMMAL's DTI head was trained on (BindingDB_Kd, 42k pairs
across 1,090 targets) is **72.8 % kinase-skewed and contains zero Nav1.8
entries** — the whole SCN family is 5 incidental rodent pairs (0.012 %). The
head was literally never shown a Nav to learn from.

**But data alone isn't sufficient either.** I tested 6 well-trained targets:
3 work brilliantly (RORC 0.97, CA2 0.87, Adrb2 0.87) but 3 don't — including
**BRAF at AUROC 0.47, the most-trained target in the entire pool**. The
threshold curve is non-monotonic:

![Threshold curve](../results/datafit_curve.png)

Practical: a Quiver Nav fine-tune is still the right move (it lifts Nav off the
0-pair floor), but it's no longer free money — plan for a held-out scaffold
AUROC ≥ 0.80 go/no-go. Separately: I tested whether the ceiling wins are
chemotype memorisation; a held-out-scaffold test refuted that (RORC AUROC 0.93
on the 94 % of binders that aren't its dominant scaffold). The wins are real
generalisation.

---

### Q2 — Does mTOR work? *(Matt — it's a Quiver target with 192 BindingDB pairs)*

**No — mTOR is the next BRAF.** AUROC drops from 0.76 on random decoys to 0.56
on MW-matched, and the off-target Δ is **inverted (−1.12)**: binders score
*lower* on mTOR than on unrelated proteins. Truncation suspect tested
(kinase-domain window, fully visible, no truncation) — AUROC stayed at **0.50**.
**Drop mTOR from any "MAMMAL is data-suited" pitch.**

---

### Q3 — Does ConPLex beat MAMMAL? *(Matt, David)*

**No, and now with more receipts.** Original test: ConPLex sits at chance on
Nav1.8 and mTOR (same as MAMMAL), loses on the 10-pair correlation
(ρ −0.03 vs MAMMAL's +0.43) and on the suzetrigine→Nav1.8 named test (worse
z-margin). **New follow-up:** I ran ConPLex on all 9 Nav paralogs (Nav1.1
through Nav1.9) — mean AUROC = 0.437, **0/9 paralogs above the useful 0.60
line, max = 0.50**. ConPLex is *pan-Nav blind*, not Nav1.8-specifically blind.
On the off-target sanity panel (Graham's protocol) the strongest "specificity"
signal in the table belongs to *ibuprofen*, not the Nav drugs — same failure
mode as MAMMAL. **Zero-shot DTI failure on ion channels is a property of the
BindingDB-trained tooling space, not MAMMAL-specific. No off-the-shelf
alternative rescues us.** Boltz-2 (different architecture) is the only
remaining unknown.

---

### Q4 — Does ADMET-AI replace the broken ClinTox? *(Matt, David)*

**Yes, via its DILI head: TPR 0.83 vs MAMMAL ClinTox's 0.08** on the 30-drug
phase5 panel. ADMET-AI earns the toxicity-gate slot.

Worth noting: ADMET-AI's *own* ClinTox endpoint also fails (TPR 0.00). The
ClinTox training data is the wrong endpoint, not just MAMMAL's head. **Use
mechanism-specific endpoints (DILI / hERG / AMES); deprecate MAMMAL ClinTox.**

---

### Q5 — Are MAMMAL embeddings really better than ESM-2? *(Matt)*

**At parity, not superiority.** The Phase 5 "MAMMAL 0.92 vs ESM-2-8M 0.88" was
on a 25-protein toy panel — never re-run on the canonical 40-gene CRISPR-N.
On the real panel: MAMMAL 0.750 NN-recall, ESM-2-650M (raw) 0.725,
**ESM-2-650M with the standard centering correction = 0.750 (tie)**. The
Sapphire embedding-layer pitch survives, but ESM-2-650M (MIT-licensed, open)
is a clean swap.

---

### Q6 — Why is BBBP "too permissive"? *(Graham, Mahdi)*

**Graham was directionally right.** Spearman(P(BBB+), MW) = −0.73 across 51
drugs. The head is a learned size + polarity exclusion gate — operative cliff
is ≳ 450 Da + polar, not "< 300 Da → brain".

**Mahdi's reframe is fully validated and now operationally usable:** 8/8
"predicted no" calls (P < 0.3) are truly non-penetrant; only 29/43 "predicted
yes" calls are actually CNS-active (67 %, marginally above base rate). **Use
BBBP as a hard negative gate, soft positive flag.**

---

### Q7 — Did PROTON get evaluated? *(Matt, David)*

**Access confirmed open** (code MIT, weights on HuggingFace, NeuroKG on Harvard
Dataverse). **Install needs Linux or AWS** — DGL ships no Apple-Silicon wheels,
from-source compile is ~1 hr, and we ran out of disk for NeuroKG + weights
anyway. Queued for the same AWS g5 box as Boltz-2 when AWS is back on. Plan
when it runs: CRISPR-N panel embedding vs MAMMAL/ESM-2, plus drug-target link
prediction for Nav1.8 / mTOR.

---

## Net strategic update

Thesis unchanged but sharper: **MAMMAL is commodity enrichment, not core
infra.** Moat stays Quiver functional trace data + V1-T. The **Quiver Nav
fine-tune is the only available lever** — but ROI-with-risk now, not free
money. ADMET-AI DILI takes over the toxicity gate. ESM-2-650M is a viable open
embedding swap. **mTOR drops from the data-suited list.** Boltz-2 and PROTON
queue for AWS.

Happy to dive into any of these.

— Rohan
