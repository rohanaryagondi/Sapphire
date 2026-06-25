# Reading the CNS trial registry as intelligence

The `clinical-trial-registry` agent reads ClinicalTrials.gov as an *analyst*, not a researcher: a termination reason, an early stop, or a status change is a **timestamped signal about what happened to a program — often before (or instead of) any publication**. All records below were pulled from the **ClinicalTrials.gov v2 REST API** (T1); each quote is the verbatim `whyStopped` (or official title) of the cited NCT, retrieved 2026-06-25.

## Termination signals by area

**Alzheimer's — the anti-amyloid Phase 3 failure wave (2019).** Aducanumab ENGAGE ([NCT02477800](https://clinicaltrials.gov/study/NCT02477800)) was terminated on a futility analysis "**not based on safety concerns**"; crenezumab CREAD ([NCT03114657](https://clinicaltrials.gov/study/NCT03114657)) was discontinued at interim as "**unlikely to meet its primary endpoint**." Both predate the later lecanemab/donanemab successes — a reminder that a target's Phase 3 failures don't necessarily kill the mechanism.

**ALS — futility + sponsor decisions.** Dexpramipexole's Phase 3 extension ([NCT01622088](https://clinicaltrials.gov/study/NCT01622088)) ended because the parent EMPOWER trial missed its endpoint; the Triumeq repurposing Phase 3 ([NCT05193994](https://clinicaltrials.gov/study/NCT05193994)) stopped at interim for "**no benefit … on survival**"; and Biogen's ataxin-2-lowering **antisense oligonucleotide** BIIB105 ([NCT04494256](https://clinicaltrials.gov/study/NCT04494256)) was terminated by "**Sponsor's decision**" — a CNS ASO-against-a-genetic-modifier program discontinued, directly relevant to a gene-medicine pipeline's risk model.

**Huntington — HTT-lowering ASOs.** Wave's allele-selective WVE-120101 (PRECISION-HD1, [NCT03225833](https://clinicaltrials.gov/study/NCT03225833)) was terminated for "**Lack of Efficacy**"; CoQ10's 2CARE Phase 3 ([NCT00608881](https://clinicaltrials.gov/study/NCT00608881)) for futility. **Registry-vs-reality caveat:** Roche's tominersen GENERATION HD1 ([NCT03761849](https://clinicaltrials.gov/study/NCT03761849)) is recorded **COMPLETED with no `whyStopped`**, even though Roche halted dosing in March 2021 — the halt lives in press/literature, *not* the structured registry. Always corroborate a high-profile program's registry status against releases.

## The key analyst lesson — read `whyStopped`, not just `status`
An "early termination" is **not** inherently bad news. The pivotal SMA trial **ENDEAR** (nusinersen, [NCT02193074](https://clinicaltrials.gov/study/NCT02193074)) is recorded "**TERMINATED**" — but the reason was a **positive** interim analysis enabling roll-over into open-label. Similarly, Ionis's MECP2-duplication biomarker study ([NCT06014541](https://clinicaltrials.gov/study/NCT06014541)) and Encoded's SCN1A+ Dravet natural-history study ([NCT04537832](https://clinicaltrials.gov/study/NCT04537832)) both ended early having **met their objectives** — positive-context terminations that *signal a program advancing*. Reading the status alone would invert the signal.

## Portfolio / business signals
A "**Business Decision**" withdrawal (Takeda's Dravet/LGS study, [NCT06395792](https://clinicaltrials.gov/study/NCT06395792)) or "Sponsor's decision" termination is a prioritization signal, not an efficacy verdict — surface it as such.

> **Scope note.** This is the trial-record / termination-signal layer. The deeper signal-types the agent can mine (protocol-amendment events, posted adverse-event tables, DSMB/interim timing from update patterns) and the published-literature behind these mechanisms (EMET) are partially-covered or pending — see `manifest.md`.
