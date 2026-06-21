# DTI training-data distribution audit — is Nav / ion-channel data even in there?

**NEXT_STEPS item 1c (Graham's hypothesis).** Characterize the dataset MAMMAL's
DTI binding head was fine-tuned on, and answer the headline: **are voltage-gated
ion channels — specifically Nav (SCN family) — represented in the training data?**

- Script: `experiments/dti_data_distribution.py` (run it; pulls the data, fetches real UniProt annotations, computes everything).
- Raw artifacts: `results/dti_train_data_per_target.csv` (per-target pair counts + UniProt name/gene/class for all 1,090 targets), `results/dti_data_distribution_20260607_045305.json` (full summary).
- Run date: 2026-06-07. Env: conda `mammal`, PyTDC, UniProt REST.

## Verdict (one line)

**Graham is right.** The DTI training pool is heavily kinase-skewed (kinases =
**72.8% of all pairs**), and **Nav1.8 (SCN10A, Q9Y5Y9) is completely absent** —
not as a target ID, and not by sequence (its 1,956-aa sequence and a 50-aa internal
probe match nothing in the data). The whole Nav/SCN family contributes **5 pairs
out of 42,236 (0.012%)**, and SCN10A specifically contributes **zero**. The observed
Nav binding failure is consistent with a **data gap, not a model limitation** — the
head was never shown a voltage-gated sodium channel to learn from. This is the
green light for the "a Quiver ion-channel fine-tune could rescue it" hypothesis.

## Dataset & schema

`DTI(name="BindingDB_Kd")` from PyTDC — the dataset the DTI head was fine-tuned on.
The MAMMAL data module (`mammal/examples/dti_bindingdb_kd/pl_data_module.py`) does
`harmonize_affinities("max_affinity")` → `convert_to_log("binding")` → split. The
published checkpoint used `cold_split`; the PEER checkpoint we deploy used a PEER
split. **Both draw from the same harmonized BindingDB_Kd pool**, so the coverage
audit (what proteins exist, ion-channel presence) is split-independent — we report
on the full harmonized pool, the universe the training share is sampled from.

| stage | pairs | unique drugs | unique targets |
|---|---|---|---|
| raw `get_data()` | 52,274 | 10,661 | 1,090 |
| harmonized (`max_affinity`, dedup dup measurements) | **42,236** | 9,887 | **1,090** |

**Schema note (good news):** TDC's columns are `Drug_ID`, `Drug` (SMILES),
`Target_ID`, `Target` (AA sequence), `Y` (–log Kd). `Target_ID` **is a UniProt
accession** (e.g. `P00918` = carbonic anhydrase II) — 1,089 of 1,090 match the
UniProt accession regex; the one exception is `nan`, plus one multi-accession
calmodulin entry `P0DP25,P0DP24,P0DP23`. Because the IDs are real accessions, the
class/ion-channel breakdown below is built on **actual UniProt annotations**
(Keywords + Protein families fetched from the UniProt REST API), not name-guessing.

## Per-target skew (tests "not evenly spread")

Strongly skewed, as hypothesized:

| metric | value |
|---|---|
| unique targets | 1,090 |
| total pairs | 42,236 |
| top **1%** of targets (11) hold | **7.1%** of pairs |
| top **10%** of targets (109) hold | **30.2%** of pairs |
| **Gini coefficient** | **0.572** |
| max / median pairs-per-target | 532 / 13.5 = **39×** |

The most-represented target alone (BRAF, 532 pairs) carries more pairs than the
entire ion-channel class (427).

### Top-20 targets

| pairs | accession | gene | protein | len |
|---|---|---|---|---|
| 532 | P15056 | BRAF | Serine/threonine-protein kinase B-raf | 766 |
| 374 | P51449 | RORC | Nuclear receptor ROR-gamma | 518 |
| 317 | P36888 | FLT3 | Receptor-type tyrosine-protein kinase FLT3 | 993 |
| 300 | P10721 | KIT | Mast/stem cell growth factor receptor Kit | 976 |
| 269 | P00918 | CA2 | Carbonic anhydrase 2 | 260 |
| 239 | P24941 | CDK2 | Cyclin-dependent kinase 2 | 298 |
| 211 | Q8K4Z4 | Adrb2 | Beta-2 adrenergic receptor (GPCR) | 418 |
| 211 | Q9JI35 | HRH3 | Histamine H3 receptor (GPCR) | 445 |
| 192 | P42345 | MTOR | Serine/threonine-protein kinase mTOR | 2549 |
| 184 | P31389 | HRH1 | Histamine H1 receptor (GPCR) | 488 |

(Full top-20 in the JSON; the tail past #10 is more kinases + GPCRs.) The top of
the distribution is exactly the data-rich oncology/CNS targets Graham predicted:
cancer kinases (BRAF, FLT3, KIT, CDK2, mTOR), nuclear receptors, and aminergic GPCRs.

## Coarse target-class breakdown

Method: classified each target by its **real UniProt Keywords + Protein-family**
string (e.g. keyword "Ion channel" / "Voltage-gated channel" → ion_channel;
"Kinase" → kinase; "G-protein coupled receptor" → gpcr). 1,089 / 1,090 targets
classified from UniProt annotations; 1 fell back to name-keyword heuristic.
**Caveat:** this is keyword/family classification, *not* a Pfam HMM assignment —
the "other" bucket is a grab-bag (oxidoreductases, transferases, hydrolases,
viral polyproteins, transporters, structural proteins, etc.), and a protein with
multiple roles is assigned by the precedence order in the script (ion-channel
checked first, then kinase, GPCR, nuclear receptor, phosphatase, protease).

| class | targets | pairs | % of pairs |
|---|---|---|---|
| **kinase** | 388 | **30,743** | **72.8%** |
| other | 419 | 5,969 | 14.1% |
| gpcr | 166 | 3,726 | 8.8% |
| nuclear_receptor | 30 | 1,041 | 2.5% |
| **ion_channel** | 47 | **427** | **1.0%** |
| protease | 34 | 302 | 0.7% |
| phosphatase | 6 | 28 | 0.1% |

Kinases are ~73% of the binding signal the head ever saw. Ion channels are ~1%.

## ION CHANNEL / NAV — the headline

Three independent angles, all agreeing:

**(a) UniProt-keyword ion channels:** 47 targets, **427 pairs (1.01% of all pairs)**.
The list is dominated by hERG/Kv potassium channels (KCNH2 45, KCNN3/SK3 40, KCNA3
27), ligand-gated channels (5-HT3 receptors, P2X purinoceptors, nAChRs, GABA-A,
glutamate receptors), TRP channels (TRPM6 72, TRPV1, TRPM8), one L-type calcium
channel (CACNA1C, 22), and CFTR (22). So the head *has* seen some channels — but
not the one we care about.

**(b) Name-keyword cross-check** on UniProt protein names (independent of the
keyword classifier): 20 targets with "channel"/"voltage-gated"/SCN/KCN/CACNA in
the name — same picture, dominated by Kv channels.

**(c) Nav / SCN family — the actual question:**
- **Nav1.8 (Q9Y5Y9 / SCN10A): ABSENT.** Not present as a target ID.
- The whole voltage-gated sodium-channel (SCN) family contributes **5 pairs total
  (0.012% of 42,236)** — one pair each for **SCN1A, SCN2A, SCN3A, SCN4A, SCN9A**,
  and notably these are mostly the **rodent** orthologs (lowercase gene symbols
  `Scn1a`/`Scn2a`/`Scn3a`, mouse/rat) — i.e. incidental, not a curated Nav effort.
- **SCN10A (Nav1.8) specifically: 0 pairs.** SCN11A (Nav1.9), the other DRG
  channel, is also absent.

**(d) Sequence angle (catches a relabeled/isoform Nav):** fetched the Nav1.8
sequence (Q9Y5Y9, **1,956 aa**) and checked the target sequences directly. The
**full sequence is NOT present**, and a **50-aa internal probe (residues 500–550)
matches no target sequence** — so Nav1.8 isn't hiding under a different ID either.
The data does contain 46 long (>1,500 aa) multidomain targets and 21 >1,900 aa
(the SCN paralogs above sit here, ~1,840–2,009 aa; plus mTOR, IP3 receptors, etc.),
so the head isn't categorically blind to long channel-shaped proteins — it just
never saw a Nav1.8.

### Why this matters

The DTI head was fine-tuned on a pool where Nav1.8 is **literally absent** and the
entire Nav family is **5 incidental, mostly-rodent pairs**. There is no training
signal from which the head could learn to discriminate Nav1.8 binders from decoys.
So the Nav binding failure we measured (Phase 1: suzetrigine→Nav1.8 fails; binder-
vs-decoy ≈ chance) is **expected from a data gap**, and is *not* evidence that
MAMMAL's architecture can't model ion channels. It is the strongest empirical case
yet that a **Quiver ion-channel / Nav fine-tune** (where off-the-shelf MAMMAL ≈
AUROC 0.5 and IBM has no head) is the move that would actually add value — exactly
the per-target-fine-tune-on-Quiver-data thesis in CLAUDE.md.

**Caveats / honesty:** (1) class breakdown is UniProt-keyword/family-based, not
Pfam HMMs — labeled as such; "other" is heterogeneous. (2) This audits the full
harmonized BindingDB_Kd pool; the actual PEER/cold *train share* is a subset (~6.5k–7.9k
pairs) of it, but coverage of a class can only shrink under sub-sampling, so "Nav
absent in the pool" ⇒ "Nav absent in any split's train set." (3) Post-cutoff drug
(suzetrigine) and the head's 1,250-aa target truncation are separate, additional
reasons Nav prediction fails — the data gap is one of several compounding factors,
but it's the one a fine-tune can fix.
