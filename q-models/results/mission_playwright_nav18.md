# MissION (portal-only SOTA oracle) on Nav1.8 — full 16-variant benchmark via Playwright, 2026-06-15

**Answering "have you used Playwright?":** yes. **MissION / Synaptica Variant Interpreter**
(`synaptica.nl/variant-interpreter`) is a JS SPA with **no API / no headless access** (curl sees ~1 KB) — the
one source in the campaign that genuinely required a browser. I drove its form with Playwright (scripted:
gene → select SCN10A → position → auto-filled reference → substitution → interpret → scrape the result) for
**all 16 SCION SCN10A/Nav1.8 variants** (the only public Nav1.8 GoF/LoF labels: 9 GoF / 7 LoF), and scored
MissION's LoGoF output against the labels. MissION confirms SCN10A coverage (11,578 variants in its DB).

## Headline
**MissION-on-Nav1.8 AUROC = 0.770 — real signal, but well below its published 0.925 within-distribution; and
it NEVER confidently calls a Nav1.8 loss-of-function (0 / 7 true LoF). Even the SOTA oracle is materially
degraded and LoF-blind on Nav1.8 → reinforces build-don't-buy on Quiver functional data, now with a number.**

| Model (GoF=positive) | AUROC on the 16 Nav1.8 variants | reference |
|---|---|---|
| **MissION** (the SOTA oracle) | **0.770** | its paper claims 0.925 (within-distribution) |
| funNCion | 0.714 | its paper claims 0.897 |
| SCION (portal's displayed score) | 0.413 | uninformative here — see caveat |

**MissION's categorical calls:** 6 GoF (5 correct, 1 wrong), **10 UNCERTAIN, 0 LoF.** Of the 7 true LoF
variants, MissION called **0 as LoF** (6 UNCERTAIN, 1 wrongly GoF). It is, on Nav1.8, a confident-GoF detector
that abstains or errs on LoF — the clinically critical direction.

## The 16 variants (MissION LoGoF score; higher = GoF)
| pos | sub | true | MissION | funNCion | SCION |
|---|---|---|---|---|---|
| 94 | Val→Gly | LoF | 0.140 UNCERTAIN | 0.012 LoF | 0.459 |
| 158 | Tyr→Asp | GoF | **0.903 GoF** | 0.005 | 1.926 |
| 242 | Ser→Thr | GoF | **0.957 GoF** | 0.580 | 0.509 |
| 388 | Leu→Met | LoF | 0.719 UNCERTAIN | 0.004 LoF | 0.870 |
| 554 | Leu→Pro | GoF | **0.959 GoF** | 0.961 GoF | 0.960 |
| 756 | Arg→Trp | LoF | 0.638 UNCERTAIN | 0.304 | 1.776 |
| 814 | Arg→His | GoF | 0.878 UNCERTAIN | 0.976 GoF | 0.085 |
| 867 | Leu→Phe | LoF | 0.409 UNCERTAIN | 0.017 LoF | 0.345 |
| 1102 | Pro→Ser | GoF | 0.735 UNCERTAIN | 0.086 | 0.814 |
| 1304 | Ala→Thr | GoF | 0.788 UNCERTAIN | 0.451 | 1.496 |
| 1518 | Val→Ile | LoF | **0.961 GoF** ✗ | 0.009 LoF | 1.981 |
| 1588 | Arg→Gln | LoF | 0.763 UNCERTAIN | 0.984 | 0.880 |
| 1639 | Asp→Asn | LoF | 0.854 UNCERTAIN | 0.316 | 1.379 |
| 1662 | Gly→Ser | GoF | 0.719 UNCERTAIN | 0.530 | 1.653 |
| 1706 | Ile→Val | GoF | **0.951 GoF** | 0.873 | 0.230 |
| 1886 | Ala→Val | GoF | **0.930 GoF** | 0.051 | 0.623 |

The one outright MissION miss is **V1518I** (Val→Ile, a near-isosteric conservative substitution) — scored
0.961 (GoF) but is a true LoF; the hardest kind of case.

## Read
- MissION carries genuine signal on Nav1.8 (0.77 > chance) but is **~0.15 AUROC below its headline** — Nav1.8
  is out-of-comfort even for the SOTA.
- More striking than the AUROC: **MissION will not commit to a LoF on Nav1.8.** For a drug-discovery program
  that needs to know whether a Nav1.8 variant *reduces* channel function, the best public tool abstains.
- This is the empirical capstone of the variant story: our own fine-tune showed cross-channel transfer to
  Nav1.8 fails (`results/variant_finetune_characterization.md`); now the SOTA portal oracle is shown to be
  degraded + LoF-blind on Nav1.8 too. **No public model — generic pLM, funNCion, our fine-tune, or MissION —
  reliably calls Nav1.8 GoF/LoF. This is a build-don't-buy capability for Quiver's functional data.**

## Caveats
- **n = 16** → wide confidence interval (AUROC 0.77 ± ~0.13); read as directional, corroborated by the
  categorical LoF-blindness (0/7) which is less sample-size-fragile.
- **Provenance/leakage unknown:** these 16 are SCION's labels; whether they overlap MissION's (undisclosed)
  training set is unknown, so 0.77 may be *optimistic*. The portal's displayed "SCION" score is a model
  output of unclear scale/orientation (0.085–1.981) and did not separate here (AUROC 0.41) — do not
  over-interpret it; the ground-truth labels are SCION's, the SCION *score* shown is a separate artifact.
- MissION is an **oracle/benchmark, not a deployable model or a data feed** (portal-only, proprietary).

**Method:** Playwright (`mcp__playwright__browser_run_code_unsafe`) scripted the SPA form for all 16 variants;
AUROC computed locally (rank-sum, GoF=positive). Variant labels: `data/cns_variants/scion/clean_tbl.csv`.
No AWS used. The other browser-gated sources (GRIN/KCNQ1/SCN-viewer) remain catalogued in
`docs/cns_data_sources.md` but, given transfer fails, are unlikely to change this conclusion.
