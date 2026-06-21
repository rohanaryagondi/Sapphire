"""Phase 6 — CROSS-MODAL ALIGNMENT in the base MAMMAL embedding space.

THE question for the "MAMMAL as Sapphire latent-space layer" pitch: does the base
458m model embed a protein target and its known small-molecule binders into a SHARED
space where binders are systematically closer to the target than matched decoys?

We test TWO operationalizations of "cross-modal proximity", because protein and SMILES
tokenize into different sub-vocabularies and raw cross-modal cosine may be meaningless:

  (A) SEPARATE-ENCODE cosine — the literal "shared latent space" claim. Embed the
      protein alone (masked mean-pool, 768-d, L2-norm) and each molecule alone, then
      score each molecule by cos(target_emb, mol_emb). AUROC(binder vs decoy) per target
      and pooled. Plus a TARGET-SPECIFICITY test: is a binder closer to its OWN target
      than to the other targets? (controls for "all molecules look alike to all proteins").

  (B) JOINT-ENCODE block alignment — the alternative the paper architecture implies.
      Co-encode protein+SMILES in ONE encoder pass (the exact DTI-task prompt, but on the
      BASE model — no DTI head). In that pass the molecule tokens have cross-attended to the
      protein tokens. Score by cos(pooled molecule-token block, pooled protein-token block).
      AUROC(binder vs decoy) per target and pooled. This is "target-conditioned" proximity.

  Diagnostics: within- vs cross-modality cosine bands (is cosine modality-dominated?),
  Cohen's d and Mann-Whitney U effect sizes, per-target AUROC distribution.

Reference prior (NOT re-run here to respect the one-model-in-RAM constraint): MAMMAL's
PURPOSE-BUILT joint binding head (DTI PEER) already gave ~0 single-target binder-vs-decoy
separation on Nav1.8 (+0.00) and mTOR (+0.10) — see results/phase2b_quiver_targets.md. So a
strong positive here would be surprising; a null is the expected, and still decision-relevant,
outcome.

MEMORY: loads ONE model (base_458m), computes everything, writes JSON, exits.

Run:  USE_TF=0 USE_FLAX=0 /opt/anaconda3/envs/mammal/bin/python experiments/phase6_crossmodal_alignment.py
"""
from __future__ import annotations
import os
os.environ.setdefault("USE_TF", "0"); os.environ.setdefault("USE_FLAX", "0")
os.environ["PYTHONUNBUFFERED"] = "1"
# This machine is under heavy memory pressure (swap ~full). MPS uses unified RAM and
# thrashes; pin to CPU with a small, fixed thread count for predictable throughput.
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
FORCE_CPU = os.environ.get("PHASE6_FORCE_CPU", "1") == "1"

import json, sys, math, functools, urllib.parse, urllib.request, random, gc
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import torch
torch.set_num_threads(max(1, min(4, (os.cpu_count() or 4))))
from mammal_quiver.embed import load_base_model, embed
from mammal_quiver.sequences import fetch_uniprot_sequence
from mammal.keys import (
    ENCODER_INPUTS_ATTENTION_MASK, ENCODER_INPUTS_STR, ENCODER_INPUTS_TOKENS,
)


def _p(*a):
    print(*a, flush=True)

random.seed(0)
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
HID = "model.out.encoder_last_hidden_state"
MASK = "data.encoder_input_attention_mask"

# Exact DTI-task joint prompt (protein + small molecule, one encoder pass), base model.
JOINT_TPL = (
    "<@TOKENIZER-TYPE=AA><MASK>"
    "<@TOKENIZER-TYPE=AA@MAX-LEN=1250><MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN><SEQUENCE_NATURAL_START>{prot}<SEQUENCE_NATURAL_END>"
    "<@TOKENIZER-TYPE=SMILES@MAX-LEN=256><MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE><SEQUENCE_NATURAL_START>{smi}<SEQUENCE_NATURAL_END>"
    "<EOS>"
)

# ---- pinned reference binders (SMILES from PubChem/ChEMBL, isomeric) for classic targets.
# These are well-characterized, on-market or tool compounds for each target family.
PIN = {
    # EGFR kinase inhibitors
    "gefitinib": "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1",
    "erlotinib": "C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1",
    "lapatinib": "CS(=O)(=O)CCNCc1ccc(-c2ccc3ncnc(Nc4ccc(OCc5cccc(F)c5)c(Cl)c4)c3c2)o1",
    "osimertinib": "C=CC(=O)Nc1cc(Nc2nccc(-c3cn(C)c4ccccc34)n2)c(OC)cc1N(C)CCN(C)C",
    "afatinib": "CN(C)C/C=C/C(=O)Nc1cc2c(Nc3ccc(F)c(Cl)c3)ncnc2cc1O[C@H]1CCOC1",
    "dacomitinib": "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1NC(=O)/C=C/CN1CCCCC1",
    # ADRB2 (beta-2 adrenergic) ligands
    "salbutamol": "CC(C)(C)NCC(O)c1ccc(O)c(CO)c1",
    "formoterol": "COc1ccc(CC(C)NCC(O)c2ccc(O)c(NC=O)c2)cc1",
    "propranolol": "CC(C)NCC(O)COc1cccc2ccccc12",
    "carvedilol": "COc1ccccc1OCCNCC(O)COc1cccc2[nH]c3ccccc3c12",
    "salmeterol": "OCc1cc(C(O)CNCCCCCCOCCCCc2ccccc2)ccc1O",
    "fenoterol": "CC(Cc1ccc(O)cc1)NCC(O)c1cc(O)cc(O)c1",
    # Nav1.8 (SCN10A) blockers
    "suzetrigine": "C[C@H]1[C@H]([C@@H](O[C@@]1(C)C(F)(F)F)C(=O)NC2=CC(=NC=C2)C(=O)N)C3=C(C(=C(C=C3)F)F)OC",
    "lidocaine": "CCN(CC)CC(=O)Nc1c(C)cccc1C",
    "mexiletine": "CC(N)COc1c(C)cccc1C",
    "ranolazine": "COc1ccccc1OCC(O)CN1CCN(CC(=O)Nc2c(C)cccc2C)CC1",
    "lacosamide": "COC[C@@H](NC(C)=O)C(=O)NCc1ccccc1",
    "carbamazepine": "NC(=O)N1c2ccccc2C=Cc2ccccc21",
    # ESR1 (estrogen receptor) ligands
    "estradiol": "C[C@]12CC[C@H]3[C@@H](CC[C@@H]4Cc5ccc(O)cc5[C@H]34)[C@@H]1CC[C@@H]2O",
    "tamoxifen": "CC/C(=C(\\c1ccccc1)c1ccc(OCCN(C)C)cc1)c1ccccc1",
    "raloxifene": "O=C(c1ccc(OCCN2CCCCC2)cc1)c1c(-c2ccc(O)cc2)sc2cc(O)ccc12",
    "bazedoxifene": "Cc1c(CN2CCCCCC2)c2ccc(O)cc2n1Cc1ccc(O)cc1",
    "fulvestrant": "OC[C@]12CC[C@H]3[C@@H](CC[C@@H]4Cc5ccc(O)cc5[C@H]34)[C@@H]1CC[C@@H]2OCCCCCCCCCS(=O)CCCC(F)(F)C(F)(F)F",
}

# target sets: (display, uniprot, family, list-of-binder-names-from-PIN-or-'curated')
TARGETS = [
    ("EGFR",    "P00533", "kinase",        ["gefitinib","erlotinib","lapatinib","osimertinib","afatinib","dacomitinib"]),
    ("ADRB2",   "P07550", "gpcr",          ["salbutamol","formoterol","propranolol","carvedilol","salmeterol","fenoterol"]),
    ("SCN10A",  "Q9Y5Y9", "ion_channel",   ["suzetrigine","lidocaine","mexiletine","ranolazine","lacosamide","carbamazepine"]),
    ("ESR1",    "P03372", "nuclear_recep", ["estradiol","tamoxifen","raloxifene","bazedoxifene","fulvestrant"]),
]


# ----------------------- stats helpers -----------------------
def auroc(scores, labels):
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return float("nan")
    gt = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return gt / (len(pos) * len(neg))


def cohens_d(a, b):
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return float("nan")
    ma, mb = sum(a) / na, sum(b) / nb
    va = sum((x - ma) ** 2 for x in a) / (na - 1)
    vb = sum((x - mb) ** 2 for x in b) / (nb - 1)
    sp = math.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2)) if (na + nb - 2) else 0.0
    return (ma - mb) / sp if sp else float("nan")


def mannwhitney_p(a, b):
    """Two-sided normal-approx Mann-Whitney U p-value (ties-corrected)."""
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        return float("nan")
    allv = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    ranks = [0.0] * len(allv); i = 0
    while i < len(allv):
        j = i
        while j + 1 < len(allv) and allv[j + 1][0] == allv[i][0]:
            j += 1
        r = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[k] = r
        i = j + 1
    R1 = sum(r for r, (_, g) in zip(ranks, allv) if g == 0)
    U1 = R1 - n1 * (n1 + 1) / 2.0
    mu = n1 * n2 / 2.0
    sigma = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12.0)
    if sigma == 0:
        return float("nan")
    z = (U1 - mu) / sigma
    return math.erfc(abs(z) / math.sqrt(2))  # two-sided


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


# ----------------------- SMILES fetch -----------------------
@functools.lru_cache(maxsize=512)
def pubchem_smiles(name):
    u = (f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/"
         f"{urllib.parse.quote(name)}/property/IsomericSMILES,CanonicalSMILES/JSON")
    try:
        with urllib.request.urlopen(u, timeout=30) as r:
            p = json.loads(r.read().decode())["PropertyTable"]["Properties"][0]
        return p.get("IsomericSMILES") or p.get("CanonicalSMILES") or p.get("SMILES")
    except Exception:
        return None


def get_smiles(name):
    return PIN.get(name) or pubchem_smiles(name)


# ----------------------- joint-encode block alignment -----------------------
@torch.no_grad()
def joint_block_cos(model, tok, prot, smi):
    """cos(pooled molecule-token block, pooled protein-token block) in one joint encoder pass.
    Returns None if the molecule got fully truncated / no atom tokens survive."""
    sd = {ENCODER_INPUTS_STR: JOINT_TPL.format(prot=prot, smi=smi), "data.sample_id": 0}
    tok(sample_dict=sd, key_in=ENCODER_INPUTS_STR, key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK, max_seq_len=1512)
    ids = list(sd[ENCODER_INPUTS_TOKENS])
    sd[ENCODER_INPUTS_TOKENS] = torch.tensor(sd[ENCODER_INPUTS_TOKENS], device=model.device)
    sd[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sd[ENCODER_INPUTS_ATTENTION_MASK], device=model.device)
    out = model.forward_encoder_only([sd])
    rec = out[0] if isinstance(out, list) else out
    h = rec[HID][0]  # (L,768)
    ss = tok.get_token_id("<SEQUENCE_NATURAL_START>")
    se = tok.get_token_id("<SEQUENCE_NATURAL_END>")
    ss_pos = [i for i, t in enumerate(ids) if t == ss]
    se_pos = [i for i, t in enumerate(ids) if t == se]
    if len(ss_pos) < 2 or len(se_pos) < 2:
        return None  # molecule block missing (e.g. truncated away)
    pb = h[ss_pos[0] + 1: se_pos[0]]            # protein residue tokens
    mb = h[ss_pos[1] + 1: se_pos[1]]            # molecule atom tokens
    if pb.shape[0] < 1 or mb.shape[0] < 1:
        return None
    pv = pb.mean(0); pv = pv / pv.norm().clamp(min=1e-9)
    mv = mb.mean(0); mv = mv / mv.norm().clamp(min=1e-9)
    return float(pv @ mv)


# ----------------------- main -----------------------
def main():
    dev = "cpu" if FORCE_CPU else None
    model, tok, dev = load_base_model(device=dev)
    _p(f"base_458m on {dev} (threads={torch.get_num_threads()}, force_cpu={FORCE_CPU})\n")

    # ---------- build datasets ----------
    # curated WDR91 + PGK1 (offline) + classic targets (pinned/fetched)
    wdr91_seq = json.load(open(REPO / "data" / "wdr91" / "wdr91_sequence.json"))["sequence"]
    wdr91_act = [x["smiles"] for x in json.load(open(REPO / "data" / "wdr91" / "wdr91_chembl_actives.json"))]
    wdr91_spr = [x["smiles"] for x in json.load(open(REPO / "data" / "wdr91" / "wdr91_spr_binders.json"))]
    decoy_pool = [x["smiles"] for x in json.load(open(REPO / "data" / "wdr91" / "wdr91_decoys.json"))]
    pgk1_lig = [x["smiles"] for x in json.load(open(REPO / "data" / "pgk2" / "pgk1_chembl_ligands.json"))]
    pgk2_seq = fetch_uniprot_sequence("P07205")  # PGK2 (the target the head was trained on); PGK1 ligands as proxy binders

    # cap decoys per target for runtime; sample a fixed shared decoy set (drug-like, target-agnostic).
    # Separate-encode (leg A) is cheap (short prompts) -> more decoys.
    # Joint-encode (leg B) is ~1512-token forward passes -> far fewer (machine is memory-bound).
    N_DECOY = 40            # leg A
    N_DECOY_JOINT = 12      # leg B subset (first N of shared_decoys)
    shared_decoys = random.sample(decoy_pool, N_DECOY)
    joint_decoys = shared_decoys[:N_DECOY_JOINT]

    datasets = []  # (name, family, seq, binder_smiles[], decoy_smiles[])
    # 1) WDR91 — strongest curated set (ChEMBL actives + SPR binders, dedup)
    wdr91_binders = list(dict.fromkeys(wdr91_act + wdr91_spr))
    datasets.append(("WDR91", "wd_repeat", wdr91_seq, wdr91_binders, shared_decoys))
    # 2) PGK1 ligands vs PGK2 sequence (homolog-family proxy) — cap binders
    datasets.append(("PGK2_PGK1lig", "kinase_metab", pgk2_seq, pgk1_lig[:40], shared_decoys))
    # 3-6) classic targets
    for disp, acc, fam, names in TARGETS:
        try:
            seq = fetch_uniprot_sequence(acc)
        except Exception as e:
            _p(f"  [skip {disp}] uniprot fetch failed: {e}")
            continue
        binders = [s for s in (get_smiles(n) for n in names) if s]
        if len(binders) < 3:
            _p(f"  [skip {disp}] only {len(binders)} binder SMILES resolved")
            continue
        datasets.append((disp, fam, seq, binders, shared_decoys))

    _p("datasets:")
    for nm, fam, seq, b, d in datasets:
        trunc = "  [PROT TRUNC>1250]" if len(seq) > 1250 else ""
        _p(f"  {nm:14s} fam={fam:13s} seq_len={len(seq):5d} n_binder={len(b):3d} n_decoy={len(d)}{trunc}")
    _p()

    # ---------- embed all proteins + all unique molecules ONCE (separate-encode) ----------
    _p("embedding proteins (separate-encode) ...")
    prot_emb = {}
    for nm, fam, seq, b, d in datasets:
        prot_emb[nm] = embed(model, tok, seq, kind="protein")

    # unique molecule set across all datasets
    all_mols = {}  # smiles -> emb
    uniq = []
    for _, _, _, b, d in datasets:
        for s in b + d:
            if s not in all_mols:
                all_mols[s] = None; uniq.append(s)
    _p(f"embedding {len(uniq)} unique molecules (separate-encode) ...")
    for i, s in enumerate(uniq):
        all_mols[s] = embed(model, tok, s, kind="smiles")
        if (i + 1) % 25 == 0:
            _p(f"  {i+1}/{len(uniq)}")
    gc.collect()

    # ---------- modality-dominance diagnostic ----------
    pe_list = list(prot_emb.values())
    me_sample = [all_mols[s] for s in random.sample(uniq, min(40, len(uniq)))]
    def pair_cos(vs):
        cs = []
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                cs.append(float(vs[i] @ vs[j]))
        return cs
    pp = pair_cos(pe_list)
    mm = pair_cos(me_sample)
    pm = [float(p @ m) for p in pe_list for m in me_sample]
    diag = {
        "within_protein_cos_mean": round(mean(pp), 4) if pp else None,
        "within_molecule_cos_mean": round(mean(mm), 4),
        "cross_modal_cos_mean": round(mean(pm), 4),
        "cross_modal_cos_min": round(min(pm), 4),
        "cross_modal_cos_max": round(max(pm), 4),
        "note": "if within-molecule >> cross-modal and cross-modal band is tight, raw cross-modal cosine is modality-dominated (uninformative for binding).",
    }
    _p(f"\ndiagnostic: within-prot cos={diag['within_protein_cos_mean']}, "
          f"within-mol cos={diag['within_molecule_cos_mean']}, "
          f"cross-modal cos={diag['cross_modal_cos_mean']} [{diag['cross_modal_cos_min']},{diag['cross_modal_cos_max']}]")

    # ---------- (A) separate-encode cross-modal proximity ----------
    _p("\n=== (A) separate-encode cross-modal proximity ===")
    perA = {}
    all_binder_cos, all_decoy_cos = [], []  # pooled (within-target z would be better; report both)
    binder_cos_by_target = {}  # for target-specificity
    for nm, fam, seq, b, d in datasets:
        pe = prot_emb[nm]
        bc = [float(pe @ all_mols[s]) for s in b]
        dc = [float(pe @ all_mols[s]) for s in d]
        binder_cos_by_target[nm] = (b, bc)
        a = auroc(bc + dc, [1] * len(bc) + [0] * len(dc))
        perA[nm] = {
            "family": fam, "n_binder": len(b), "n_decoy": len(d),
            "auroc": round(a, 4),
            "mean_binder_cos": round(mean(bc), 4), "mean_decoy_cos": round(mean(dc), 4),
            "delta": round(mean(bc) - mean(dc), 4),
            "cohens_d": round(cohens_d(bc, dc), 3),
            "mannwhitney_p": round(mannwhitney_p(bc, dc), 4),
        }
        all_binder_cos += bc; all_decoy_cos += dc
        _p(f"  {nm:14s} AUROC={a:.3f}  d={perA[nm]['cohens_d']:+.2f}  "
              f"binder={perA[nm]['mean_binder_cos']:+.3f} decoy={perA[nm]['mean_decoy_cos']:+.3f} "
              f"p={perA[nm]['mannwhitney_p']:.3f}")
    pooledA = {
        "auroc": round(auroc(all_binder_cos + all_decoy_cos,
                             [1] * len(all_binder_cos) + [0] * len(all_decoy_cos)), 4),
        "cohens_d": round(cohens_d(all_binder_cos, all_decoy_cos), 3),
        "mannwhitney_p": round(mannwhitney_p(all_binder_cos, all_decoy_cos), 4),
        "mean_auroc_across_targets": round(mean([perA[nm]["auroc"] for nm in perA]), 4),
    }
    _p(f"  POOLED AUROC={pooledA['auroc']:.3f}  mean-of-target AUROC={pooledA['mean_auroc_across_targets']:.3f}  d={pooledA['cohens_d']:+.2f}")

    # ---------- target-specificity: is a binder closest to its OWN target? ----------
    _p("\n=== (A2) target-specificity (binder vs all target proteins) ===")
    tnames = [nm for nm, *_ in datasets]
    spec_correct, spec_total, ranks = 0, 0, []
    for nm in tnames:
        b, _ = binder_cos_by_target[nm]
        for s in b:
            sims = {t: float(prot_emb[t] @ all_mols[s]) for t in tnames}
            order = sorted(tnames, key=lambda t: -sims[t])
            rank = order.index(nm) + 1
            ranks.append(rank)
            spec_correct += (order[0] == nm); spec_total += 1
    specA = {
        "rank1_accuracy": round(spec_correct / spec_total, 4) if spec_total else None,
        "mean_rank_of_true_target": round(mean(ranks), 3) if ranks else None,
        "n_targets": len(tnames), "chance_rank1": round(1 / len(tnames), 4),
        "chance_mean_rank": round((len(tnames) + 1) / 2, 3),
        "n_binders_tested": spec_total,
    }
    _p(f"  rank-1 acc={specA['rank1_accuracy']} (chance {specA['chance_rank1']}); "
          f"mean rank of true target={specA['mean_rank_of_true_target']} (chance {specA['chance_mean_rank']}, lower=better)")

    # ---------- (B) joint-encode block alignment ----------
    # Memory-bound: cap binders + use the small joint_decoys subset (each pass = 1512-token fwd).
    N_BINDER_JOINT = 15
    _p(f"\n=== (B) joint-encode molecule-block vs protein-block alignment "
       f"(<= {N_BINDER_JOINT} binders + {len(joint_decoys)} decoys/target) ===")
    perB = {}
    allB_b, allB_d = [], []
    n_pass = 0
    for nm, fam, seq, b, d in datasets:
        bj = b[:N_BINDER_JOINT]
        bc, dc = [], []
        for s in bj:
            c = joint_block_cos(model, tok, seq, s)
            n_pass += 1
            if c is not None:
                bc.append(c)
        for s in joint_decoys:
            c = joint_block_cos(model, tok, seq, s)
            n_pass += 1
            if c is not None:
                dc.append(c)
        gc.collect()
        a = auroc(bc + dc, [1] * len(bc) + [0] * len(dc))
        perB[nm] = {
            "family": fam, "n_binder": len(bc), "n_decoy": len(dc),
            "auroc": round(a, 4),
            "mean_binder_cos": round(mean(bc), 4), "mean_decoy_cos": round(mean(dc), 4),
            "delta": round(mean(bc) - mean(dc), 4),
            "cohens_d": round(cohens_d(bc, dc), 3),
            "mannwhitney_p": round(mannwhitney_p(bc, dc), 4),
        }
        allB_b += bc; allB_d += dc
        _p(f"  {nm:14s} AUROC={a:.3f}  d={perB[nm]['cohens_d']:+.2f}  "
           f"binder={perB[nm]['mean_binder_cos']:+.3f} decoy={perB[nm]['mean_decoy_cos']:+.3f} "
           f"p={perB[nm]['mannwhitney_p']:.3f}  [{n_pass} passes so far]")
    pooledB = {
        "auroc": round(auroc(allB_b + allB_d, [1] * len(allB_b) + [0] * len(allB_d)), 4),
        "cohens_d": round(cohens_d(allB_b, allB_d), 3),
        "mannwhitney_p": round(mannwhitney_p(allB_b, allB_d), 4),
        "mean_auroc_across_targets": round(mean([perB[nm]["auroc"] for nm in perB]), 4),
    }
    _p(f"  POOLED AUROC={pooledB['auroc']:.3f}  mean-of-target AUROC={pooledB['mean_auroc_across_targets']:.3f}  d={pooledB['cohens_d']:+.2f}")

    # ---------- verdict logic ----------
    def verdict(pooled_auroc, mean_auroc):
        # well above chance and consistent -> alignment exists; near 0.5 -> none
        if mean_auroc >= 0.70 and pooled_auroc >= 0.70:
            return "ALIGNMENT PRESENT (binders systematically closer than decoys)"
        if mean_auroc >= 0.60:
            return "WEAK alignment (modest binder>decoy ordering)"
        return "NO meaningful alignment (binder vs decoy ~ chance)"

    result = {
        "phase": "phase6_crossmodal_alignment",
        "timestamp": TS, "device": dev,
        "model": "base_458m (no task head)",
        "n_targets": len(datasets),
        "targets": [{"name": nm, "family": fam, "seq_len": len(seq),
                     "truncated_protein": len(seq) > 1250,
                     "n_binder": len(b), "n_decoy": len(d)} for nm, fam, seq, b, d in datasets],
        "decoys_per_target_legA": N_DECOY,
        "decoys_per_target_legB": len(joint_decoys),
        "binders_cap_legB": N_BINDER_JOINT,
        "modality_diagnostic": diag,
        "A_separate_encode_cosine": {"per_target": perA, "pooled": pooledA,
                                     "verdict": verdict(pooledA["auroc"], pooledA["mean_auroc_across_targets"])},
        "A2_target_specificity": specA,
        "B_joint_encode_block_alignment": {"per_target": perB, "pooled": pooledB,
                                           "verdict": verdict(pooledB["auroc"], pooledB["mean_auroc_across_targets"])},
        "reference_prior": "DTI PEER (purpose-built joint binding head) gave ~0 single-target binder-vs-decoy separation: Nav1.8 +0.00, mTOR +0.10 (results/phase2b_quiver_targets.md).",
    }
    outp = REPO / "results" / f"phase6_crossmodal_alignment_{TS}.json"
    outp.write_text(json.dumps(result, indent=2))
    _p(f"\nVERDICT (A separate-encode): {result['A_separate_encode_cosine']['verdict']}")
    _p(f"VERDICT (B joint-encode):     {result['B_joint_encode_block_alignment']['verdict']}")
    _p(f"saved -> {outp}")


if __name__ == "__main__":
    main()
