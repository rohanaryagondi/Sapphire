"""Boltz-2 CO-FOLDING on the HARD CNS ion channels where SEQUENCE-DTI is at chance.

WHY
===
`results/cns_dti_characterization.md` showed that off-the-shelf SEQUENCE-DTI
(BALM cosine + PLAPT affinity, both BindingDB-pretrained) is **at or below chance**
on the CNS ion-channel family Quiver actually cares about:

    target              family    BALM   PLAPT   seq-DTI read
    CACNA1C (Cav1.2)    ion ch    0.204  0.307   sub-chance (worst)
    GRIN1   (NMDA NR1)  ion ch    0.32   0.41    sub-chance
    SCN5A   (Nav1.5)    ion ch    0.459  0.429   chance
    SCN10A  (Nav1.8)    ion ch    0.780  0.480   BALM works, PLAPT collapses

The family averages to ~0.50 because sequence models generalise where the
training data lives (kinase/GPCR-rich BindingDB) and collapse on state/use-
dependent ion-channel pharmacology. The open question this eval answers:

    **Does STRUCTURE (Boltz-2 co-folding + affinity head) recover binder-vs-decoy
    signal on the exact channels where SEQUENCE fails?**

Boltz-2 is structurally different from the seq-DTI tools (AlphaFold3-class
co-fold + affinity head, not a contrastive PLM on BindingDB), so it does not
share their training-data gap. If Boltz-2 beats chance on Cav1.2 / GRIN1 / Nav1.5
that is the first off-the-shelf model that works on these targets. If it ALSO
fails, the conclusion sharpens: nothing off-the-shelf works on hard CNS ion
channels and the Quiver fine-tune is the only lever.

PANEL (SMALL + BOUNDED — Boltz is minutes/complex and channels are ~2000 aa)
===========================================================================
3 hard targets (seq-DTI at/below chance) + 1 positive control:
    CACNA1C  (Cav1.2,  Q13936, ~2221 aa) -- seq-DTI 0.20, the worst
    GRIN1    (NMDA NR1, Q05586, ~938 aa)  -- seq-DTI 0.32
    SCN5A    (Nav1.5,  Q14524, ~2016 aa)  -- seq-DTI 0.46
    SCN10A   (Nav1.8,  Q9Y5Y9, ~1956 aa)  -- POSITIVE CONTROL (Boltz got 0.714 before)

Per target: <= MAX_PER_TARGET (default 10 = ~5 actives + ~5 decoys) compounds
-> at most 4 x 10 = 40 co-folds. Actives/decoys pulled from ChEMBL on-instance
(same pattern as cns_dti_benchmark_eval.py: pchembl>=ACTIVE_PCHEMBL actives,
same-target ChEMBL inactives as decoys, else property-matched cross-target decoys).
Full WT sequences from UniProt REST (NO truncation — that is the whole point of
testing structure; Boltz handles the long channels or OOMs, and an OOM is a result).

EXECUTION (reuses aws/boltz_runner.py VERBATIM)
===============================================
This script DOES NOT re-implement Boltz invocation. It:
  1. Builds the panel (ChEMBL + UniProt), caps it HARD at MAX_PER_TARGET.
  2. Writes a complexes JSON in boltz_runner.py's exact schema
     ({name, target, drug, label, protein_seq, smiles}).
  3. Shells out to boltz_runner.py (`python boltz_runner.py <complexes.json>`)
     with BOLTZ_OUT / BOLTZ_CACHE / per-complex timeout env vars set. The runner
     already wraps every co-fold in a wall-clock timeout, atomically writes
     results.json, and classifies OOM / timeout / CLI-mismatch / MSA failure and
     records prob_binder=None on any failure (n_scored / n_skipped / skip_reason
     fall straight out of its per-complex `failure_class` + null prob_binder).
  4. Reads the runner's results.json, computes per-target binder-vs-decoy AUROC
     (on Boltz `prob_binder` = affinity_probability_binary), and compares to the
     seq-DTI baselines from cns_dti_characterization.md.

Per-complex timeout (PAIR_TIMEOUT_S, default 600 s) is passed to the runner via
BOLTZ_PAIR_TIMEOUT_S so a single ~2000-aa OOM/hang SKIPS that complex rather than
sinking the whole run. The preflight (first complex) gets a longer cap for the
cold ~10 GB weight download + ColabFold MSA queue.

Writes consolidated JSON to env OUT (default /root/boltzcns_out/boltz_cns_result.json).
Every stage is try/except-guarded; partial results always upload.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUT", "/root/boltzcns_out/boltz_cns_result.json"))
# Where boltz_runner.py is staged (launcher aws s3 cp's it next to this eval).
RUNNER = os.environ.get("BOLTZ_RUNNER", "/opt/boltz_runner.py")
# Boltz weight cache + the runner's working/output dir (on the EBS / local disk).
BOLTZ_CACHE = os.environ.get("BOLTZ_CACHE", "/root/boltz_cache")
BOLTZ_OUT = os.environ.get("BOLTZ_OUT", "/root/boltz_out")

# Per-complex wall-clock cap (the spec's 600 s) -> SKIP+record on timeout/OOM.
PAIR_TIMEOUT_S = int(os.environ.get("PAIR_TIMEOUT_S", "600"))
# First complex covers cold ~10 GB weight download + ColabFold MSA queue.
PREFLIGHT_TIMEOUT_S = int(os.environ.get("PREFLIGHT_TIMEOUT_S", "3600"))

# ChEMBL knobs (same semantics as cns_dti_benchmark_eval.py, but a HARD small cap).
ACTIVE_PCHEMBL = float(os.environ.get("ACTIVE_PCHEMBL", "6.0"))     # >= => active (~<=1 uM)
INACTIVE_PCHEMBL = float(os.environ.get("INACTIVE_PCHEMBL", "5.0"))  # <= => ChEMBL inactive
MAX_PER_TARGET = int(os.environ.get("MAX_PER_TARGET", "10"))        # HARD cap compounds/target
N_ACTIVES = int(os.environ.get("N_ACTIVES", "5"))                   # ~5 actives/target
N_DECOYS = int(os.environ.get("N_DECOYS", "5"))                     # ~5 decoys/target
DECOY_TANIMOTO_MAX = float(os.environ.get("DECOY_TANIMOTO_MAX", "0.35"))
RNG = np.random.default_rng(int(os.environ.get("SEED", "20260614")))

BINDING_TYPES = ["IC50", "Ki", "Kd"]

# ---------------------------------------------------------------------------
# THE HARD PANEL. gene -> (uniprot, fallback_chembl, family-note, seq-DTI baseline).
# 3 hard targets where seq-DTI is at/below chance + 1 positive control (Nav1.8).
# seq_dti_baseline: best of (BALM, PLAPT) from cns_dti_characterization.md, for the
# headline "does structure beat sequence" comparison. control=True is the Nav1.8 PC.
# ---------------------------------------------------------------------------
PANEL = {
    "CACNA1C": {"uniprot": "Q13936", "chembl": "CHEMBL1940",    # Cav1.2
                "label_short": "Cav1.2", "seq_dti_balm": 0.204, "seq_dti_plapt": 0.307,
                "control": False},
    "GRIN1":   {"uniprot": "Q05586", "chembl": "CHEMBL1907594",  # NMDA NR1
                "label_short": "NMDA-NR1", "seq_dti_balm": 0.32, "seq_dti_plapt": 0.41,
                "control": False},
    "SCN5A":   {"uniprot": "Q14524", "chembl": "CHEMBL1980",     # Nav1.5
                "label_short": "Nav1.5", "seq_dti_balm": 0.459, "seq_dti_plapt": 0.429,
                "control": False},
    "SCN10A":  {"uniprot": "Q9Y5Y9", "chembl": "CHEMBL5451",     # Nav1.8 -- POSITIVE CONTROL
                "label_short": "Nav1.8", "seq_dti_balm": 0.780, "seq_dti_plapt": 0.480,
                "control": True, "boltz_prior": 0.714},
}


# ---------------------------------------------------------------------------
# AUROC (rank-sum, average-rank ties). Reused verbatim from cns_dti_benchmark_eval.py.
# ---------------------------------------------------------------------------
def auroc(labels, scores):
    labels = np.asarray(labels, dtype=float)
    scores = np.asarray(scores, dtype=float)
    pos = scores[labels == 1]
    neg = scores[labels == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=float)
    s = scores[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        ranks[order[i:j + 1]] = avg
        i = j + 1
    rank_pos = ranks[labels == 1].sum()
    n_pos, n_neg = len(pos), len(neg)
    return float((rank_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


# ---------------------------------------------------------------------------
# UniProt WT-sequence fetch (pattern from cns_dti_benchmark_eval.py). FULL sequence,
# no truncation: testing whether structure helps means giving Boltz the whole channel.
# ---------------------------------------------------------------------------
def fetch_uniprot_seq(acc):
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "boltz-cns-eval/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        fasta = r.read().decode("utf-8")
    return "".join(l.strip() for l in fasta.splitlines() if not l.startswith(">"))


# ---------------------------------------------------------------------------
# ChEMBL access (chembl_webresource_client) — same approach as cns_dti_benchmark_eval.py.
# ---------------------------------------------------------------------------
def resolve_chembl_id(meta):
    from chembl_webresource_client.new_client import new_client
    acc = meta["uniprot"]
    try:
        hits = list(new_client.target.filter(
            target_components__accession=acc,
            target_type="SINGLE PROTEIN",
            organism="Homo sapiens",
        ).only(["target_chembl_id", "target_type", "organism", "pref_name"]))
        for h in hits:
            tid = h.get("target_chembl_id")
            if tid:
                return tid, "resolved_by_uniprot_accession"
    except Exception as e:
        print(f"[warn] ChEMBL target resolve failed for {acc}: {e}", flush=True)
    if meta.get("chembl"):
        return meta["chembl"], "hardcoded_fallback"
    return None, None


def fetch_activities(chembl_id):
    """{smiles: best_pchembl} over IC50/Ki/Kd activities with a non-null pchembl."""
    from chembl_webresource_client.new_client import new_client
    qs = new_client.activity.filter(
        target_chembl_id=chembl_id,
        standard_type__in=BINDING_TYPES,
        pchembl_value__isnull=False,
    ).only(["canonical_smiles", "pchembl_value", "standard_type"])
    best = {}
    for a in qs:
        smi = a.get("canonical_smiles")
        pv = a.get("pchembl_value")
        if not smi or pv is None:
            continue
        try:
            pv = float(pv)
        except (TypeError, ValueError):
            continue
        if smi not in best or pv > best[smi]:
            best[smi] = pv
    return best


# ---------------------------------------------------------------------------
# RDKit property + fingerprint helpers for property-matched decoys (verbatim).
# ---------------------------------------------------------------------------
def mol_props(smi):
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    return {"mw": Descriptors.MolWt(m), "logp": Descriptors.MolLogP(m),
            "hbd": Lipinski.NumHDonors(m), "hba": Lipinski.NumHAcceptors(m)}


def morgan_fp(smi):
    from rdkit import Chem
    from rdkit.Chem import AllChem
    m = Chem.MolFromSmiles(smi)
    if m is None:
        return None
    return AllChem.GetMorganFingerprintAsBitVect(m, 2, 2048)


def property_matched_decoys(active_smiles, active_props, candidate_pool, n_needed):
    from rdkit import DataStructs
    if not active_props:
        return []
    mw = np.array([p["mw"] for p in active_props])
    logp = np.array([p["logp"] for p in active_props])
    hbd = np.array([p["hbd"] for p in active_props])
    hba = np.array([p["hba"] for p in active_props])
    env = {
        "mw": (mw.mean(), max(mw.std(), 50.0) * 1.5),
        "logp": (logp.mean(), max(logp.std(), 1.0) * 1.5),
        "hbd": (hbd.mean(), max(hbd.std(), 1.0) * 2.0),
        "hba": (hba.mean(), max(hba.std(), 1.0) * 2.0),
    }
    active_fps = [fp for fp in (morgan_fp(s) for s in active_smiles) if fp is not None]
    picked = []
    pool = list(candidate_pool)
    RNG.shuffle(pool)
    for smi in pool:
        if smi in active_smiles:
            continue
        p = mol_props(smi)
        if p is None:
            continue
        if abs(p["mw"] - env["mw"][0]) > env["mw"][1]:
            continue
        if abs(p["logp"] - env["logp"][0]) > env["logp"][1]:
            continue
        if abs(p["hbd"] - env["hbd"][0]) > env["hbd"][1]:
            continue
        if abs(p["hba"] - env["hba"][0]) > env["hba"][1]:
            continue
        fp = morgan_fp(smi)
        if fp is None:
            continue
        if active_fps:
            sims = DataStructs.BulkTanimotoSimilarity(fp, active_fps)
            if max(sims) >= DECOY_TANIMOTO_MAX:
                continue
        picked.append(smi)
        if len(picked) >= n_needed:
            break
    return picked


# ---------------------------------------------------------------------------
# Build the SMALL per-target {actives, decoys, seq} sets, capped HARD.
# ---------------------------------------------------------------------------
def build_panels():
    built = {}
    dropped = {}
    raw_actives = {}     # gene -> {smiles: pchembl} (also the cross-target decoy pool)
    raw_inactives = {}

    # Pass 1: ChEMBL actives / inactives.
    for gene, meta in PANEL.items():
        try:
            cid, src = resolve_chembl_id(meta)
            if not cid:
                dropped[gene] = "no ChEMBL target id"
                continue
            best = fetch_activities(cid)
            actives = {s: v for s, v in best.items() if v >= ACTIVE_PCHEMBL}
            inactives = {s: v for s, v in best.items() if v <= INACTIVE_PCHEMBL}
            # keep the STRONGEST N_ACTIVES (most confident binders) -> tiny panel.
            if len(actives) > N_ACTIVES:
                actives = dict(sorted(actives.items(), key=lambda kv: -kv[1])[:N_ACTIVES])
            raw_actives[gene] = actives
            raw_inactives[gene] = inactives
            built[gene] = {"chembl_id": cid, "chembl_id_source": src,
                           "uniprot": meta["uniprot"], "label_short": meta["label_short"],
                           "control": meta.get("control", False),
                           "n_actives_pre_drop": len(actives),
                           "n_chembl_inactives": len(inactives)}
            print(f"[chembl] {gene} ({cid}, {src}): {len(actives)} actives(<=N) / "
                  f"{len(inactives)} inactives", flush=True)
        except Exception as e:
            dropped[gene] = f"fetch error: {type(e).__name__}: {e}"
            print(f"[warn] {gene} fetch failed: {e}", flush=True)

    # Drop targets with NO actives at all (can't score; need >=1 each side ideally).
    for gene in list(built.keys()):
        if built[gene]["n_actives_pre_drop"] < 1:
            dropped[gene] = "no actives at pchembl threshold"
            built.pop(gene)
            raw_actives.pop(gene, None)

    # Cross-target active pool for property-matched fallback decoys.
    global_pool = [s for acts in raw_actives.values() for s in acts.keys()]

    # Pass 2: decoys (capped at N_DECOYS) + FULL UniProt sequence.
    for gene in list(built.keys()):
        try:
            meta = PANEL[gene]
            actives = raw_actives[gene]
            inactives = raw_inactives.get(gene, {})
            decoy_smiles = []
            decoy_source = None
            # (1) true same-target ChEMBL inactives (cleanest decoys), weakest first.
            if len(inactives) >= 1:
                items = sorted(inactives.items(), key=lambda kv: kv[1])
                decoy_smiles = [s for s, _ in items[:N_DECOYS]]
                decoy_source = "chembl_inactives_same_target"
            # (2) top up with property-matched cross-target decoys if short.
            if len(decoy_smiles) < N_DECOYS:
                active_smiles = set(actives.keys())
                active_props = [p for p in (mol_props(s) for s in actives) if p is not None]
                cand = [s for g2, acts in raw_actives.items() if g2 != gene
                        for s in acts.keys()] or list(global_pool)
                extra = property_matched_decoys(
                    active_smiles, active_props, cand, N_DECOYS - len(decoy_smiles))
                for s in extra:
                    if s not in decoy_smiles:
                        decoy_smiles.append(s)
                decoy_source = (decoy_source + "+property_matched"
                                if decoy_source else "property_matched_cross_target")

            # FULL WT sequence (no truncation — Boltz gets the whole channel).
            seq, seq_source = None, None
            try:
                seq = fetch_uniprot_seq(meta["uniprot"])
                if seq and len(seq) > 30:
                    seq_source = "uniprot_rest"
            except Exception as e:
                print(f"[warn] UniProt fetch failed {gene} ({meta['uniprot']}): {e}", flush=True)
            if not seq:
                dropped[gene] = f"no protein sequence (UniProt {meta['uniprot']})"
                built.pop(gene)
                continue

            # HARD cap: total compounds <= MAX_PER_TARGET.
            act_list = list(actives.keys())
            cap_act = min(len(act_list), N_ACTIVES, MAX_PER_TARGET)
            act_list = act_list[:cap_act]
            cap_dec = min(len(decoy_smiles), MAX_PER_TARGET - len(act_list))
            decoy_smiles = decoy_smiles[:max(cap_dec, 0)]

            built[gene].update({
                "seq": seq, "seq_len": len(seq), "seq_source": seq_source,
                "actives": act_list, "decoys": decoy_smiles,
                "decoy_source": decoy_source,
                "n_actives": len(act_list), "n_decoys": len(decoy_smiles),
            })
            print(f"[panel] {gene} ({meta['label_short']}): {len(act_list)} actives / "
                  f"{len(decoy_smiles)} decoys ({decoy_source}); seq_len={len(seq)}",
                  flush=True)
        except Exception as e:
            dropped[gene] = f"decoy/seq build error: {type(e).__name__}: {e}"
            print(f"[warn] {gene} build failed: {e}\n{traceback.format_exc()[:600]}", flush=True)
            built.pop(gene, None)

    return built, dropped


# ---------------------------------------------------------------------------
# Emit boltz_runner.py's complexes JSON. Schema EXACTLY matches the runner's
# _required = ("name", "protein_seq", "smiles") + the optional target/drug/label
# it preserves into each record. Ordering matters for the runner's preflight:
# put the POSITIVE-CONTROL active FIRST so the first (longest-timeout) complex is
# the most likely to succeed and warm the weight + MSA caches.
# ---------------------------------------------------------------------------
def build_complexes(panels):
    rows = []
    ordered = sorted(panels.items(), key=lambda kv: (not kv[1].get("control", False)))
    for gene, p in ordered:
        short = p["label_short"]
        # control's active(s) first within its block (so complex #0 is a real binder).
        for k, smi in enumerate(p["actives"]):
            rows.append({"name": f"{gene}_act{k}", "target": gene, "label_short": short,
                         "drug": f"act{k}", "label": 1,
                         "protein_seq": p["seq"], "smiles": smi})
        for k, smi in enumerate(p["decoys"]):
            rows.append({"name": f"{gene}_dec{k}", "target": gene, "label_short": short,
                         "drug": f"dec{k}", "label": 0,
                         "protein_seq": p["seq"], "smiles": smi})
    return rows


# ---------------------------------------------------------------------------
# Run boltz_runner.py over the complexes JSON (REUSE ITS EXACT CLI/IO). The runner
# wraps each co-fold in a wall-clock timeout, classifies OOM/timeout/MSA failure,
# atomically writes results.json, and sets prob_binder=None on any failure.
# ---------------------------------------------------------------------------
def run_boltz(complexes, complexes_path):
    Path(complexes_path).write_text(json.dumps(complexes, indent=2))
    if not Path(RUNNER).is_file():
        raise FileNotFoundError(f"boltz_runner.py not staged at {RUNNER}")
    env = dict(os.environ)
    # Map this eval's knobs onto the runner's exact env interface.
    env["BOLTZ_OUT"] = BOLTZ_OUT
    env["BOLTZ_CACHE"] = BOLTZ_CACHE
    env["BOLTZ_PAIR_TIMEOUT_S"] = str(PAIR_TIMEOUT_S)
    env["BOLTZ_PREFLIGHT_TIMEOUT_S"] = str(PREFLIGHT_TIMEOUT_S)
    env.setdefault("USE_TF", "0")
    env.setdefault("USE_FLAX", "0")
    cmd = [sys.executable, RUNNER, str(complexes_path)]
    print(f"[boltz] launching runner: {' '.join(cmd)} "
          f"(BOLTZ_OUT={BOLTZ_OUT}, pair_timeout={PAIR_TIMEOUT_S}s)", flush=True)
    # The runner enforces its own per-complex timeouts; we give the whole pass a
    # generous outer ceiling = n complexes x (pair timeout + slack) + preflight.
    n = len(complexes)
    outer = PREFLIGHT_TIMEOUT_S + n * (PAIR_TIMEOUT_S + 120) + 600
    try:
        rc = subprocess.run(cmd, env=env, timeout=outer).returncode
    except subprocess.TimeoutExpired:
        print(f"[boltz] OUTER TIMEOUT after {outer}s — reading whatever the runner "
              "atomically wrote so far", flush=True)
        rc = 124
    # The runner writes results.json (atomic) regardless; read it back.
    runner_results = Path(BOLTZ_OUT) / "results.json"
    if not runner_results.is_file():
        raise FileNotFoundError(f"runner produced no results.json at {runner_results} (rc={rc})")
    return rc, json.loads(runner_results.read_text())


# ---------------------------------------------------------------------------
# Score the runner output -> per-target binder-vs-decoy AUROC + skip accounting +
# the headline structure-vs-sequence comparison.
# ---------------------------------------------------------------------------
def score(runner_payload, panels):
    records = runner_payload.get("complexes", [])
    by_target = {}    # gene -> {pos:[], neg:[], n_scored, n_skipped, skips:[]}
    for r in records:
        gene = r.get("target")
        if gene is None:
            # fall back to name prefix (gene_act0 / gene_dec0)
            gene = r.get("name", "").split("_")[0]
        bt = by_target.setdefault(gene, {"pos": [], "neg": [], "n_scored": 0,
                                         "n_skipped": 0, "skips": []})
        prob = r.get("prob_binder")
        if prob is None:
            bt["n_skipped"] += 1
            fc = r.get("failure_class", {}) or {}
            reason = ("oom" if fc.get("oom") else
                      "timeout" if fc.get("timeout") else
                      "cuda_error" if fc.get("cuda_other") else
                      "msa_failure" if fc.get("msa_failure") else
                      "flag_mismatch" if fc.get("flag_mismatch") else
                      "parse_or_other_fail")
            bt["skips"].append({"name": r.get("name"), "label": r.get("label"),
                                "reason": reason, "rc": r.get("rc"),
                                "seq_len": r.get("seq_len")})
            continue
        bt["n_scored"] += 1
        if r.get("label") == 1:
            bt["pos"].append(float(prob))
        elif r.get("label") == 0:
            bt["neg"].append(float(prob))

    per_target = {}
    for gene, meta in PANEL.items():
        bt = by_target.get(gene)
        if bt is None:
            per_target[gene] = {"label_short": meta["label_short"], "auroc": None,
                                "note": "target absent from runner output (dropped pre-Boltz)"}
            continue
        pos, neg = bt["pos"], bt["neg"]
        labels = [1] * len(pos) + [0] * len(neg)
        scores = pos + neg
        a = auroc(labels, scores) if (pos and neg) else None
        best_seq = max(meta.get("seq_dti_balm") or 0.0, meta.get("seq_dti_plapt") or 0.0)
        per_target[gene] = {
            "label_short": meta["label_short"],
            "control": meta.get("control", False),
            "auroc": (round(a, 4) if a is not None else None),
            "n_pos_scored": len(pos), "n_neg_scored": len(neg),
            "n_scored": bt["n_scored"], "n_skipped": bt["n_skipped"],
            "skips": bt["skips"],
            "mean_pos_prob": round(float(np.mean(pos)), 4) if pos else None,
            "mean_neg_prob": round(float(np.mean(neg)), 4) if neg else None,
            "separation": (round(float(np.mean(pos) - np.mean(neg)), 4)
                           if pos and neg else None),
            "seq_dti_baseline_best": round(best_seq, 4),
            "seq_dti_balm": meta.get("seq_dti_balm"),
            "seq_dti_plapt": meta.get("seq_dti_plapt"),
            "boltz_prior": meta.get("boltz_prior"),
            "boltz_beats_sequence": (a is not None and a > best_seq),
            "boltz_beats_chance": (a is not None and a >= 0.60),
        }
    return per_target


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    Path(BOLTZ_OUT).mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    results = {
        "task": ("Boltz-2 co-folding on the HARD CNS ion channels where SEQUENCE-DTI "
                 "is at/below chance (Cav1.2, NMDA-NR1, Nav1.5) + Nav1.8 positive "
                 "control. Headline: does STRUCTURE recover binder-vs-decoy signal "
                 "where SEQUENCE fails?"),
        "panel_definition": {g: {"uniprot": m["uniprot"], "label_short": m["label_short"],
                                 "control": m.get("control", False),
                                 "seq_dti_balm": m.get("seq_dti_balm"),
                                 "seq_dti_plapt": m.get("seq_dti_plapt"),
                                 "boltz_prior": m.get("boltz_prior")}
                             for g, m in PANEL.items()},
        "config": {"active_pchembl_min": ACTIVE_PCHEMBL,
                   "inactive_pchembl_max": INACTIVE_PCHEMBL,
                   "max_per_target": MAX_PER_TARGET, "n_actives": N_ACTIVES,
                   "n_decoys": N_DECOYS, "pair_timeout_s": PAIR_TIMEOUT_S,
                   "preflight_timeout_s": PREFLIGHT_TIMEOUT_S,
                   "boltz_runner": RUNNER, "boltz_cache": BOLTZ_CACHE,
                   "boltz_out": BOLTZ_OUT},
        "seq_dti_receipts": "results/cns_dti_characterization.md",
    }

    def dump():
        OUT.write_text(json.dumps(results, indent=2, default=str))

    # 1) Build the small panel (guarded).
    try:
        panels, dropped = build_panels()
        results["dropped_targets"] = dropped
        results["built_targets"] = {
            g: {"chembl_id": p["chembl_id"], "chembl_id_source": p["chembl_id_source"],
                "label_short": p["label_short"], "uniprot": p["uniprot"],
                "n_actives": p["n_actives"], "n_decoys": p["n_decoys"],
                "decoy_source": p["decoy_source"], "seq_len": p["seq_len"],
                "seq_source": p["seq_source"], "control": p.get("control", False)}
            for g, p in panels.items()}
        results["n_targets_built"] = len(panels)
        dump()
    except Exception as e:
        results["build_error"] = f"{type(e).__name__}: {e}"
        results["traceback"] = traceback.format_exc()[:2000]
        dump()
        print(f"[done-early] build failed: {e}", flush=True)
        return
    if not panels:
        results["fatal"] = "no targets built; nothing to co-fold"
        dump()
        print("[done-early] no targets built", flush=True)
        return

    # 2) Build complexes JSON + run boltz_runner.py (reusing its exact CLI/IO).
    complexes = build_complexes(panels)
    results["n_complexes"] = len(complexes)
    results["complex_order"] = [c["name"] for c in complexes]
    dump()
    complexes_path = Path(BOLTZ_OUT) / "cns_complexes.json"
    try:
        rc, runner_payload = run_boltz(complexes, complexes_path)
        results["boltz_runner_rc"] = rc
        results["boltz_infra"] = runner_payload.get("infra")
        results["boltz_wall_time_sec"] = runner_payload.get("wall_time_sec")
        results["n_complexes_in_runner_output"] = len(runner_payload.get("complexes", []))
        dump()
    except Exception as e:
        results["boltz_run_error"] = f"{type(e).__name__}: {e}"
        results["traceback"] = traceback.format_exc()[:2000]
        dump()
        print(f"[done-early] boltz run failed: {e}", flush=True)
        return

    # 3) Score (guarded) -> per-target AUROC + skip accounting + headline.
    try:
        per_target = score(runner_payload, panels)
        results["per_target"] = per_target

        scored = {g: r for g, r in per_target.items() if r.get("auroc") is not None}
        hard = {g: r for g, r in scored.items() if not r.get("control")}
        results["headline"] = {
            "structure_vs_sequence": {
                g: {"label": r["label_short"], "boltz_auroc": r["auroc"],
                    "seq_dti_best": r["seq_dti_baseline_best"],
                    "boltz_beats_sequence": r["boltz_beats_sequence"],
                    "boltz_beats_chance(>=0.60)": r["boltz_beats_chance"]}
                for g, r in scored.items()},
            "n_hard_targets_scored": len(hard),
            "n_hard_boltz_beats_chance": sum(1 for r in hard.values()
                                             if r.get("boltz_beats_chance")),
            "n_hard_boltz_beats_sequence": sum(1 for r in hard.values()
                                               if r.get("boltz_beats_sequence")),
            "control_nav18": (scored.get("SCN10A", {}).get("auroc")),
            "control_nav18_prior_boltz": PANEL["SCN10A"].get("boltz_prior"),
            "total_scored": sum(r.get("n_scored", 0) for r in per_target.values()),
            "total_skipped": sum(r.get("n_skipped", 0) for r in per_target.values()),
        }
        # one-line verdict for the log
        nbc = results["headline"]["n_hard_boltz_beats_chance"]
        nh = results["headline"]["n_hard_targets_scored"]
        results["verdict"] = (
            f"Boltz-2 beats chance (AUROC>=0.60) on {nbc}/{nh} hard CNS ion-channel "
            f"targets where seq-DTI is at/below chance. "
            f"Nav1.8 control AUROC={results['headline']['control_nav18']} "
            f"(prior Boltz {PANEL['SCN10A'].get('boltz_prior')}).")
    except Exception as e:
        results["score_error"] = f"{type(e).__name__}: {e}"
        results["traceback"] = traceback.format_exc()[:2000]

    results["runtime_sec"] = round(time.time() - t0, 1)
    dump()
    print(f"[done] wrote {OUT}", flush=True)
    print(json.dumps(results.get("headline", {}), indent=2, default=str), flush=True)
    print(results.get("verdict", ""), flush=True)


if __name__ == "__main__":
    main()
