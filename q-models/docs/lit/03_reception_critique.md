# Reception & Critique — what the field has said about MAMMAL

**Lane: reception & critique. Written 2026-06-01.** What has the biomedical-ML community actually
done with IBM MAMMAL (`ibm/biomed.omics.bl.sm.ma-ted-458m`, npj Drug Discovery 2026, arXiv
2410.22367; code `github.com/BiomedSciAI/biomed-multi-alignment`) since publication, and what
limitations have been reported? Companion to `docs/FINDINGS.md` (our empirical Quiver results),
`01_*` (paper deep-dive), `02_competitive_landscape.md` (vs the field), `04_domain_context.md`.

**Bar, per the team mantra:** "state-of-the-art on shit is still shit." This doc asks a narrower
question than "is it good" — it asks "has *anyone else* tested whether it's good?" The answer is
the headline finding.

---

## The one-paragraph verdict

**MAMMAL has had almost no independent external scrutiny. That is the single most important finding
in this lane.** Fifteen-plus months after the preprint (Oct 2024) and ~1 month after the npj
version, the paper has ~6–8 citations (OpenAlex: 6 on the preprint, 0 on the npj record yet; Semantic
Scholar lists ~8) — and **every one of them either lists MAMMAL in a survey, cites it as
prior-art in a related-work section, or names it as one option in a multimodal-reasoning pipeline.
None independently benchmark, reproduce, stress-test, or report failure modes of MAMMAL.** The
GitHub repo (107 stars, 29 forks) has had **3 issues in its entire lifetime** — all basic usage
questions, zero bug reports or critiques. The HuggingFace base model (~2,280 downloads/month, 48
likes) has 6 "discussions," all of which are README/maintenance PRs plus one interview request — no
reported defects. **No independent blog, benchmark, or critical evaluation of MAMMAL exists in the
public record as of this writing.** Consequently, *the most rigorous external audit of MAMMAL that
exists is this Quiver project itself* (`docs/FINDINGS.md`) — the field has not done the work, so
"reported limitations" are overwhelmingly limitations the *authors* disclosed or that *we* found, not
limitations the community surfaced. There is **no v2 and no model larger than 458M**; the per-target
`wdr91_asms`/`pgk2_del_cdd` heads are **undocumented orphan uploads** trained on borrowed public
DEL/ASMS data, with no model card and no accompanying paper.

---

## 1. Citation footprint — thin, and entirely passive

Verified via OpenAlex (`W4404344191` = arXiv preprint; `W7160131947` = npj version) and the
Semantic Scholar Graph API on 2026-06-01.

| Source | Citation count | Notes |
|---|---|---|
| OpenAlex (arXiv preprint) | **6** | published 2024 |
| OpenAlex (npj version) | **0** | published 2026, too new to have accrued indexed citations |
| Semantic Scholar (preprint) | **~8** | includes bioRxiv items OpenAlex hadn't indexed |

**What cites it (the actual citing works, characterized):**

| Citing work | Venue / year | How it uses MAMMAL |
|---|---|---|
| *Scientific Large Language Models: A Survey on Biological & Chemical Domains* | ACM Computing Surveys, 2025 | **Survey** — lists MAMMAL among many models. Passive. |
| *Enhancing foundation models for scientific discovery via multimodal knowledge graph representations* | J. Web Semantics, 2024 | Related-work / KG framing. Passive. |
| *BioVERSE: Representation Alignment of Biomedical Modalities to LLMs* | arXiv, 2025 | Cites as prior multimodal model; **does not benchmark against it** (verified: no MAMMAL comparison in the text). |
| *Bio-BLIP: A Multimodal Architecture for…Genomic Variant Interpretation* | bioRxiv, 2026 | Prior-art citation in a competing multimodal architecture. |
| *Multi-omics feature engineering driven by biomedical foundation models improves drug-response prediction* | Scientific Reports, 2026 | Closest to actual use — uses foundation-model features; MAMMAL is one of several, not the focus. |
| *Leveraging LLMs to predict antibody activity against influenza A hemagglutinin* | Comput. Struct. Biotechnol. J., 2025 | Cites in antibody-modeling context. |
| *AI models: transforming…diagnosis…of gastrointestinal cancers* | Molecular Cancer, 2026 | Review. Passive. |
| *Perspective on Bias in Biomedical AI* | 2026 | Perspective piece. Passive. |

**Read:** the citation pattern is "named in passing." There is **no second group that downloaded
MAMMAL, ran it on their own data, and published whether it held up.** For a model claiming SOTA on
9/11 drug-discovery tasks, the absence of any independent reproduction or head-to-head benchmark 15+
months out is itself a signal — either the community hasn't found it compelling enough to test, or
the unified-prompt interface raises the friction of using it as a baseline (you can't drop it into a
standard pipeline the way you can ESM-2). Either way: **the SOTA badges remain author-reported and
externally unverified by anyone but us.**

---

## 2. Community / repo activity — actively maintained by IBM, near-zero external engagement

Verified via the GitHub API and HuggingFace on 2026-06-01.

**GitHub `BiomedSciAI/biomed-multi-alignment`:**
- 107 stars, 29 forks, Apache-2.0, created 2024-10-27, **last pushed 2026-05-28** → IBM *is* still
  maintaining it (recent commits), so it is not abandonware.
- **Total issues ever opened: 3.** Two open (#42 "Embedding Extraction Code" — a usage question
  about how to pull a small-molecule embedding; #39's sibling), one closed (#39 "Finetuning for
  BBBP" — a user noting the BBBP head ships *no config file* and that they "had issues finetuning"
  it, contrasting with the protein-solubility task which worked). That is the entire external
  bug/issue history. **No reported correctness failures, no performance complaints.**
- Note #39 is a real, if minor, externally-reported friction: the published BBBP finetune lacks a
  reproducible training config — consistent with our own observation that the MoleculeNet heads are
  under-documented relative to the protein heads.

**HuggingFace `ibm-research/biomed.omics.bl.sm.ma-ted-458m` (base):**
- ~2,280 downloads/month, 48 likes, 8 listed finetunes, released 2024-10-28, Apache-2.0.
- 6 "community" items — all README PRs / a pipeline-tag PR / an interview request. **Zero defect
  reports.** Download volume is modest-but-real and is almost certainly driven by the published task
  heads (DTI, BBBP, etc.), not the base model.

**Read:** the engagement profile is "a few hundred curious downloaders a month, no community of
practice." Nobody is filing the kind of edge-case bug reports that accumulate around a model people
actually deploy in anger (cf. the ESM/AlphaFold issue trackers with thousands of issues). For Quiver
this matters operationally: **if we hit a problem, there is no community to draw on** — we found this
firsthand (the macOS TF-deadlock, the PEER-vs-cold-split checkpoint trap, the vestigial-scalar-head
trap on the per-target heads — all undocumented, all solved in-house; see `CLAUDE.md` gotchas).

---

## 3. Reported limitations — almost all author-disclosed or found by us, not by the field

Because no external group has audited MAMMAL, "known limitations" decompose into three buckets.

### 3a. Limitations the *authors* disclosed (verified, arXiv 2410.22367 v2/v3 + npj 2026)
- **No free-text modality.** The model has no PubMed/text input; the authors flag adding it as
  future work ("enabling pretraining on extensive biomedical text sources like PubMed…incorporation
  of free-text segments into prompts").
- **No scalar outputs in encoder-decoder (generative) mode** — "an improvement that we intend to add
  in future generations." This is exactly the trap we hit on the per-target heads (the scalar head is
  vestigial; you must read a *generated token* probability). The authors knew the limitation; they
  just never documented that it applies to the `wdr91`/`pgk2` heads.
- **DNA is not yet a domain** — listed as a desired future extension. (IBM's DNA work lives in the
  *separate* `biomed.multi.omic` family, not MAMMAL — see §5.)
- **Only 2 of 11 benchmark tasks were "comparable," not new SOTA** — the paper is honest that it does
  not win everywhere. Notably (per our `01_*`/`02_*` analysis) the DTI task is one where the
  task-specific PEER baseline is competitive/better, and our Phase 1 reproduced DTI NRMSE ~0.88 which
  is only ~9% better than predicting the mean. The paper's framing ("SOTA on 9/11") is accurate but
  the *magnitude* of several wins is small.

### 3b. Limitations *we* found that the field has not (see `docs/FINDINGS.md` — the real external audit)
These are not in the literature; they exist only because Quiver did the work. Briefly, so this doc
stands alone:
- **Classification heads emit uncalibrated hard 0/1 labels** (BBBP 95% / ClinTox 100% saturated),
  not usable probabilities — and **fail out-of-distribution** despite SOTA benchmark AUROC (BBBP
  false-positive bias TNR 0.70; ClinTox 0% sensitivity to *external* clinical toxics = memorization).
- **DTI single-target binder triage ≈ chance** on real targets (Nav1.8/mTOR); not a truncation
  artifact. Useful only as a coarse cross-target re-rank.
- **Compound embeddings lose to Morgan fingerprints** (0.72 vs 0.96 same-class NN).
- **Per-target heads recognize their trained chemotype, not novel hits or potency** (no graded
  ranking; one head — WDR91 — barely fires).
- **Input-form fragility**: predictions can flip across valid protonation/salt forms of the same
  molecule.
- **Meta-finding: benchmark AUROC ≠ deployable per-compound filter.** This is the single most
  important critique of MAMMAL and it is *ours*, not the field's.

### 3c. Structural critique (this lane's contribution)
- **The unified-prompt interface is a double-edged sword for adoption.** It is the model's headline
  differentiator, but it also raises the cost of using MAMMAL as a *baseline* in someone else's
  paper (you can't `model.encode(seq)` like ESM-2; you must learn the token/scalar prompt grammar and
  the per-head readout quirks). This plausibly explains the near-total absence of independent
  benchmarking — and is a soft strike against it as shared infrastructure.

---

## 4. The per-target heads (`wdr91_asms`, `pgk2_del_cdd`) — provenance traced, documentation absent

This was a specific investigation target. **Verified findings:**

- **They are NOT part of the MAMMAL paper.** Full-text search of arXiv 2410.22367 (v2/v3) for
  `WDR91`, `PGK2`, `PGK1`, `CACHE`, `AIRCHECK`, `DEL`, `DNA-encoded library`, `ASMS`, `affinity
  selection mass spec` returns **zero hits**. (Michal Ozery-Flato *is* a listed MAMMAL author, which
  is the only link.) These heads are not in any published MAMMAL benchmark.
- **They are undocumented orphan uploads.** `michalozeryflato/…wdr91_asms` on HuggingFace has **no
  model card, 0 likes, ~6 downloads/month**. No README, no dataset link, no paper, no training recipe.
  `pgk2_del_cdd` is the same. We confirmed this directly.
- **Provenance (high-confidence inference, from the data the heads are named after):**
  - **`wdr91_asms`** → WDR91, **ASMS** = affinity-selection mass-spec. WDR91 is the target of the
    public **AIRCHECK** Open-DEL-ML effort: Wellnitz et al., *"Enabling Open Machine Learning of
    DNA-Encoded Library Selections…"* (J. Med. Chem. 2025, doi 10.1021/acs.jmedchem.5c01972; PMC12557371;
    ChemRxiv 2024), which deposited a 375,595-molecule WDR91 DEL dataset (binary labels, multiple
    fingerprint feature types) in AIRCHECK, building on the first-in-class WDR91 ligand paper (Ahmad
    et al. 2023, doi 10.1021/acs.jmedchem.3c01471 — the actives source our Phase 3 used). **Important
    correction to avoid conflation:** that Wellnitz/AIRCHECK paper is a **UNC / SGC-Toronto / HitGen /
    Pfizer / Vector** effort using **LightGBM on chemical fingerprints — NOT IBM, NOT MAMMAL.** IBM
    almost certainly *reused the public AIRCHECK WDR91 data* to fine-tune a MAMMAL head; the two
    efforts share the target and the data, not the authorship or the model.
  - **`pgk2_del_cdd`** → PGK2, **DEL**, **CDD** (almost certainly Collaborative Drug Discovery, the
    data platform). This maps cleanly onto **CACHE Challenge #7** ("Finding selective inhibitors of
    PGK2 for non-hormonal contraception," Conscience/Gates Foundation), which released **1,388 hPGK2
    DEL hits (≥5 reads, de-enriched vs the PGK1 homolog, untested off-DNA)**. That "1388 hits" figure
    matches *exactly* the dataset our `phase3_pgk2_indist.py` already used — confirming the head was
    trained/evaluated on the public CACHE #7 PGK2 DEL data.
- **What this means.** The per-target heads are **demonstrations on borrowed public benchmark data,
  not productized capabilities and not peer-reviewed.** They show IBM *can* fine-tune MAMMAL per
  target (the existence proof our Phase 3 confirmed — modestly), but there is **no documentation, no
  validation paper, and no claim of generalization** behind them. Anyone treating them as
  ready-to-use binder oracles is over-reading two undocumented uploads. (Our Phase 3/4 read: chemotype
  re-recognition, ~5× top-5% enrichment at best, no potency ranking, one of the two heads near-broken.)

---

## 5. Is there a v2 or a larger model? — No.

Verified against IBM Research's Biomedical Foundation Models page, the HF model family, and the
paper. **458M is the only MAMMAL size; there is no MAMMAL v2.** For context, IBM's broader BMFM
family (a *different* lineage, not MAMMAL successors):

| IBM model | Size | Modality | Relation to MAMMAL |
|---|---|---|---|
| `biomed.sm.mv-te-84m` | 84M | small molecules (multi-view) | **Predecessor/sibling**, not MAMMAL. (Carries the same `wdr91`/`pgk2` targets but ships `.ckpt`-only, not standard-loadable — see survey.) |
| `biomed.omics.bl.sm.ma-ted-458m` | **458M** | proteins + small molecules + scRNA (MAMMAL) | **This is MAMMAL. The largest.** |
| `biomed.multi.omic` (DNA 113M / RNA 110M) | 110–113M | genomic/transcriptomic | **Separate family** — IBM's "DNA as a domain" lives here, not in MAMMAL. |

No scaling roadmap, successor announcement, or larger checkpoint is referenced anywhere public. The
arXiv has v1/v2/v3 revisions of the *same* 458M paper; "v3" is a manuscript revision, not a model
version. **Takeaway for Quiver:** what we have evaluated is what exists — there is no bigger MAMMAL
coming that would change the verdict.

---

## 6. Known failure modes others reported — essentially none (and that's the finding)

To state it plainly so it isn't mistaken for an oversight: **the external community has reported no
failure modes.** Not because the model has none (we found several real ones), but because **almost
nobody outside IBM has put it through its paces in public.** The one externally-reported friction is
GitHub issue #39 (the BBBP finetune ships no training config and was hard to reproduce) — a
documentation gap, not a model defect.

This asymmetry is the strategic point for the MAMMAL-vs-Sapphire framing: **a model with SOTA badges
but no independent validation, a 3-issue tracker, and a few hundred monthly downloads is "published,
not adopted."** It is commodity enrichment that the field is *aware of* but has not *embraced* —
which is fully consistent with `docs/FINDINGS.md`'s verdict reached from the opposite direction
(empirical testing). Two independent lines of evidence — our experiments and the field's silence —
converge on the same read.

---

## 7. Sources (all verified 2026-06-01)

- Paper: arXiv 2410.22367 (v1 Oct 2024 → v3); npj Drug Discovery 2026, doi 10.1038/s44386-026-00047-4.
- Citations: OpenAlex `W4404344191` (preprint, 6 cites) / `W7160131947` (npj, 0); Semantic Scholar
  Graph API citations endpoint for `arXiv:2410.22367` (~8 citing works, all passive/survey/related-work).
- Repo: `github.com/BiomedSciAI/biomed-multi-alignment` (107★, 29 forks, 3 lifetime issues, last push
  2026-05-28). Issues #39 (BBBP finetune config), #42 (embedding extraction) — usage questions only.
- HuggingFace: `ibm-research/biomed.omics.bl.sm.ma-ted-458m` (~2,280 dl/mo, 48 likes, 6 maintenance
  "discussions", 8 finetunes); `michalozeryflato/…wdr91_asms` (no model card, 0 likes, ~6 dl/mo).
- Per-target provenance: Wellnitz et al., J. Med. Chem. 2025 (Open DEL-ML / AIRCHECK; UNC/SGC/HitGen/
  Pfizer/Vector; **LightGBM on fingerprints, not MAMMAL**) doi 10.1021/acs.jmedchem.5c01972 (PMC12557371);
  Ahmad et al. 2023 (first-in-class WDR91 ligand) doi 10.1021/acs.jmedchem.3c01471; CACHE Challenge #7
  PGK2 (cache-challenge.org / Conscience, 1388 hPGK2 DEL hits de-enriched vs PGK1).
- Model family / no-v2: IBM Research "Biomedical Foundation Models" project page (lists 84M sm,
  458M MAMMAL, 110–113M DNA/RNA — no larger MAMMAL).
- Press (promotional only, no independent critique found): IBM Think "open-source biomedical
  foundation models"; Startup Fortune coverage — both restate IBM's own SOTA claims.

**Verified vs speculative, flagged inline.** Speculative items: the precise training recipe of the
per-target heads (no model card — provenance inferred from target/data naming + the matching 1388-hit
PGK2 dataset, high confidence but not documented by IBM); the *reason* for low external uptake (the
unified-prompt-interface-as-adoption-friction argument is our inference, not a stated fact).
