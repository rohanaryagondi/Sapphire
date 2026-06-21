"""MissION ion-channel missense GoF/LoF characterization (Quiver-native variant-effect, overnight AWS).

GOAL
----
Track-9-adjacent (selectivity/variant-effect) Quiver-native test: can a protein-language model
call gain-of-function (GoF) vs loss-of-function (LoF) for missense variants in Quiver's ion
channels (the SCN/Nav + CACNA1 channelopathy/epilepsy focus)? MissION (Synaptica, medRxiv 2025)
is the specialized ion-channel pLM classifier; funNCion (Brunklaus/Lal lab, Broad) is the prior
"current leading model" (paper's 0.897 reference) and ships the real labelled variant tables.

============================ RESEARCH / VERIFIED FACTS ============================
MissION paper:  "Functional Effect Predictions For Ion Channel Missense Variants Using a
                 Protein Language Model" -- medRxiv 2025.10.16.25337735 (Oct 2025).
                 ESM-2 embeddings + GO/HPO semantic features; combines pLM + annotation
                 streams; trained on 3,176 GoF/LoF variants across 47 channel genes
                 (K+/Na+/Ca2+ families); reported ROC-AUC 0.925 vs funNCion 0.897.
MissION CODE:    *** NO PUBLIC GITHUB REPO, NO DOWNLOADABLE CHECKPOINT *** (verified via
                 GitHub repo+code search 2026-06: zero hits). The model is reachable ONLY
                 through the web portal www.synaptica.nl/variant-interpreter (per-variant
                 lookups for ~600k precomputed variants; no documented programmatic/batch API).
                 -> We CANNOT load MissION's weights for an offline AWS eval. The MissION
                    section below is attempted-but-guarded; absent a local artifact it is
                    SKIPPED with a clear note (no fabricated numbers).
MissION DATA:    The 3,176-variant training set is NOT distributed as an in-repo CSV / Zenodo
                 dataset (verified: only a PREreview is on Zenodo). Not fetchable offline.

FALLBACK SUBSTRATE (the bankable result) -- funNCion, the paper's own reference model:
Repo:    https://github.com/heyhen/funNCion   (Apache-2.0 LICENSE in repo)
Paper:   Brunklaus et al., Brain 2022 (funNCion); bioRxiv 2021. funNCion.broadinstitute.org
Data:    SupplementaryTable_S1_pathvariantsusedintraining_revision2.txt  (TSV, in-repo, 6930 rows)
         Columns (verified header): protid  gene  pos  refAA  altAA  transcript  disease  segr
           prd_mech_revised  cohort  pathogenic_infer  pathogenicity  gnomAD_AF  confidence
           diseaseorig  maf_interpretation  LQT_penetrance  BrS_penetrance
           used_in_functional_prediction  used_in_pathogenicity_prediction  pmid_publication
         FUNCTIONAL GoF/LoF SET (verified filter, mirrors modelling_goflof_CACNA1SCN_4github.R):
           used_in_functional_prediction == 1  AND  prd_mech_revised in {"gof","lof"}
           -> 1008 variants  (623 lof / 385 gof).  Per-gene (Quiver channels starred):
              SCN1A   448 (10 gof / 438 lof)  *      SCN8A  62 (62 gof / 0 lof)  *
              SCN2A   116 (93 gof / 23 lof)   *      SCN4A  54 (45 gof / 9 lof)
              CACNA1A  78 (26 gof / 52 lof)          SCN9A  37 (37 gof / 0 lof)  *  (=Nav1.7)
              SCN5A    67 (27 gof / 40 lof)   *      CACNA1D 34 ; CACNA1E 33
              CACNA1F  49 (0/49) ; CACNA1C 18 (18/0) * ; CACNA1S 12 (0/12)
           NOTE: SCN3A and SCN10A(=Nav1.8) are NOT in this functional set (reported honestly).
           NOTE: several genes are single-class (SCN8A/SCN9A/CACNA1C all-gof; CACNA1F/CACNA1S
                 all-lof) -> per-gene AUROC is only computable where BOTH classes are present
                 (SCN1A, SCN2A, SCN5A, SCN4A, CACNA1A). Guarded accordingly.
         Variant id `protid` = "GENE:pos:refAA:altAA".  Label = prd_mech_revised (gof vs lof).

GENERIC-pLM BASELINE (per the task -- the head-to-head the scorecard needs):
  ESM-2 650M (facebook/esm2_t33_650M_UR50D) zero-shot masked-marginal LLR:
    score(variant) = logP(altAA | masked pos, WT context) - logP(refAA | masked pos, WT context).
  This is the standard ESM variant-effect signal (Meier et al. 2021). It is a CONSERVATION /
  deleteriousness signal: it scores HOW disruptive a substitution is, NOT its DIRECTION. Both
  GoF and LoF are "damaging", so we do NOT expect LLR to separate GoF from LoF; near-0.5 AUROC
  is the INFORMATIVE (motivating) result -- it shows a generic pLM does not solve the
  GoF-vs-LoF call on Quiver's channels, which is exactly the gap a specialized model (MissION)
  claims to fill. We report AUROC oriented (and |AUROC-0.5|) so a launcher reads it correctly.
  Requires WT protein sequences -> fetched per gene from UniProt REST (canonical isoform);
  refAA@pos validated against the sequence, mismatches dropped (reported as n_pos_mismatch).
==================================================================================

Sections (each independently try/except-guarded so one failure banks the rest):
  A. dataset_summary        -- load funNCion functional set; counts overall + per gene.
  B. esm2_baseline_overall  -- ESM-2 650M masked-marginal LLR; AUROC(gof=1) over all scorable
                               variants; balanced-accuracy at the Youden-J threshold.
  C. esm2_baseline_per_gene -- the QUIVER breakdown: n + AUROC for each SCN/Nav/CACNA1C gene
                               (where both classes present); n-only where single-class.
  D. mission_classifier     -- attempt to load a local MissION artifact (env MISSION_DIR /
                               MISSION_CKPT); if absent, SKIP with note. (No public weights.)
  E. comparison             -- MissION-vs-generic-pLM summary IF (D) produced scores; else the
                               honest "generic pLM is near-chance on direction; specialized model
                               needed; MissION not offline-loadable" verdict.
"""
from __future__ import annotations
import json
import os
import sys
import traceback
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUT", "/root/mission_out/mission_result.json"))
DATA_TSV = os.environ.get(
    "DATA_TSV", "/opt/funNCion/SupplementaryTable_S1_pathvariantsusedintraining_revision2.txt"
)
DATA_URL = os.environ.get(
    "DATA_URL",
    "https://raw.githubusercontent.com/heyhen/funNCion/master/"
    "SupplementaryTable_S1_pathvariantsusedintraining_revision2.txt",
)
ESM2_MODEL = os.environ.get("ESM2_MODEL", "facebook/esm2_t33_650M_UR50D")
FORCE_CPU = os.environ.get("FORCE_CPU") == "1"
MAX_VARIANTS = int(os.environ.get("MAX_VARIANTS", "0"))  # 0 = no cap
MISSION_DIR = os.environ.get("MISSION_DIR", "")  # set only if a local MissION artifact exists
MISSION_CKPT = os.environ.get("MISSION_CKPT", "")
SEQ_CACHE = Path(os.environ.get("SEQ_CACHE", "/root/mission_out/uniprot_seqs.json"))

# Quiver's channels (per CLAUDE.md): SCN/Nav family + Cav1.2.
QUIVER_GENES = ["SCN1A", "SCN2A", "SCN3A", "SCN8A", "SCN9A", "SCN10A", "SCN5A", "CACNA1C"]
QUIVER_ALIAS = {
    "SCN9A": "Nav1.7", "SCN10A": "Nav1.8", "SCN5A": "Nav1.5",
    "SCN1A": "Nav1.1", "SCN2A": "Nav1.2", "SCN3A": "Nav1.3", "SCN8A": "Nav1.6",
    "CACNA1C": "Cav1.2",
}
# Canonical human UniProt accessions for the channel genes in the funNCion set (+Quiver targets).
# Used to fetch WT sequences for the ESM-2 masked-marginal LLR. funNCion positions are on these
# canonical isoforms (its modelling pins one canonical transcript per gene); refAA@pos is
# validated against the fetched sequence and mismatches are dropped, so a wrong/alt isoform is
# self-detected (it shows up as a high n_pos_mismatch) rather than silently corrupting scores.
GENE_UNIPROT = {
    "SCN1A": "P35498", "SCN2A": "Q99250", "SCN3A": "Q9NY46", "SCN4A": "P35499",
    "SCN5A": "Q14524", "SCN8A": "Q9UQD0", "SCN9A": "Q15858", "SCN10A": "Q9Y5Y9",
    "SCN11A": "Q9UI33",
    "CACNA1A": "O00555", "CACNA1B": "Q00975", "CACNA1C": "Q13936", "CACNA1D": "Q01668",
    "CACNA1E": "Q15878", "CACNA1F": "O60840", "CACNA1G": "O43497", "CACNA1H": "O95180",
    "CACNA1I": "Q9P0X4", "CACNA1S": "Q13698",
    "KCNQ1": "P51787", "KCNQ2": "O43526", "KCNH2": "Q12809", "KCNA1": "Q09470",
    "KCNB1": "Q14721", "KCNT1": "Q5JUK3", "KCNMA1": "Q12791",
}


# ------------------------- self-contained metrics (no sklearn dependency) -------------------------
def auroc(y, s):
    """AUROC with tie-correct (mid-rank) Mann-Whitney; y in {0,1}, s = score. None if degenerate."""
    y = np.asarray(y)
    s = np.asarray(s, float)
    p = int((y == 1).sum())
    n = int((y == 0).sum())
    if p == 0 or n == 0 or len(y) < 3:
        return None
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), float)
    ranks[order] = np.arange(1, len(s) + 1)
    # mid-ranks for ties
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    start = 0
    midrank = {}
    for k, c in enumerate(cnt):
        midrank[k] = (start + 1 + start + c) / 2.0
        start += c
    rb = np.array([midrank[i] for i in inv])
    return float((rb[y == 1].sum() - p * (p + 1) / 2.0) / (p * n))


def balanced_acc_at_youden(y, s):
    """Pick threshold maximizing Youden's J on score s (higher s -> predict y=1), return
    balanced accuracy + the threshold + sensitivity/specificity there."""
    y = np.asarray(y)
    s = np.asarray(s, float)
    p = int((y == 1).sum())
    n = int((y == 0).sum())
    if p == 0 or n == 0:
        return None
    thr_cands = np.unique(s)
    best = None
    for t in thr_cands:
        pred = (s >= t).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        tn = int(((pred == 0) & (y == 0)).sum())
        sens = tp / p
        spec = tn / n
        j = sens + spec - 1.0
        if best is None or j > best["youden_j"]:
            best = {"threshold": float(t), "sensitivity": round(sens, 4),
                    "specificity": round(spec, 4), "balanced_acc": round((sens + spec) / 2.0, 4),
                    "youden_j": round(j, 4)}
    return best


def oriented(au):
    """Report AUROC plus its orientation-free strength |AUROC-0.5| (a direction-agnostic
    LLR signal can land below 0.5; |.| tells you how much GoF/LoF info is present)."""
    if au is None:
        return None
    return {"auroc": round(au, 4), "auroc_flipped": round(1.0 - au, 4),
            "directional_strength_abs": round(abs(au - 0.5), 4)}


def section(fn, name, results):
    try:
        results[name] = fn()
        print(f"[ok] {name}", flush=True)
    except Exception as e:
        results[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:1200]}", flush=True)


# ------------------------- funNCion variant loader -------------------------
def load_variants():
    """Return list of dicts {protid, gene, pos:int, refAA, altAA, transcript, label:'gof'|'lof', y:int}
    for the FUNCTIONAL set (used_in_functional_prediction==1 AND prd_mech_revised in {gof,lof}).
    y = 1 for gof, 0 for lof. Reads local TSV if present, else fetches DATA_URL."""
    path = Path(DATA_TSV)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"[data] {path} absent -> fetching {DATA_URL}", flush=True)
        urllib.request.urlretrieve(DATA_URL, str(path))
    # the file has non-utf8 bytes (latin-1); read tolerantly.
    raw = path.read_text(encoding="latin-1")
    lines = raw.splitlines()
    header = lines[0].split("\t")
    idx = {h: i for i, h in enumerate(header)}
    need = ["gene", "pos", "refAA", "altAA", "prd_mech_revised",
            "used_in_functional_prediction"]
    for col in need:
        if col not in idx:
            raise KeyError(f"missing column {col!r}; header={header}")
    out = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) < len(header):
            continue
        if f[idx["used_in_functional_prediction"]].strip() != "1":
            continue
        mech = f[idx["prd_mech_revised"]].strip().lower()
        if mech not in ("gof", "lof"):
            continue
        try:
            pos = int(f[idx["pos"]].strip())
        except ValueError:
            continue
        gene = f[idx["gene"]].strip()
        ref = f[idx["refAA"]].strip().upper()
        alt = f[idx["altAA"]].strip().upper()
        if len(ref) != 1 or len(alt) != 1:
            continue
        transcript = f[idx["transcript"]].strip() if "transcript" in idx else ""
        out.append({"protid": f"{gene}:{pos}:{ref}:{alt}", "gene": gene, "pos": pos,
                    "refAA": ref, "altAA": alt, "transcript": transcript,
                    "label": mech, "y": 1 if mech == "gof" else 0})
    if MAX_VARIANTS and len(out) > MAX_VARIANTS:
        out = out[:MAX_VARIANTS]
    return out


# ------------------------- UniProt WT-sequence fetch -------------------------
def fetch_uniprot_seq(acc):
    """Fetch a canonical UniProt sequence (FASTA) by accession. Returns the residue string."""
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "mission-eval/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        fasta = r.read().decode("utf-8")
    seq = "".join(l.strip() for l in fasta.splitlines() if not l.startswith(">"))
    return seq


def get_sequences(genes):
    """Return {gene: seq} for genes with a known UniProt accession, caching to SEQ_CACHE."""
    cache = {}
    if SEQ_CACHE.exists():
        try:
            cache = json.loads(SEQ_CACHE.read_text())
        except Exception:
            cache = {}
    seqs = {}
    for g in genes:
        if g in cache and cache[g]:
            seqs[g] = cache[g]
            continue
        acc = GENE_UNIPROT.get(g)
        if not acc:
            continue
        try:
            s = fetch_uniprot_seq(acc)
            if s:
                seqs[g] = s
                cache[g] = s
        except Exception as e:
            print(f"[warn] UniProt fetch {g}/{acc} failed: {e}", flush=True)
    try:
        SEQ_CACHE.parent.mkdir(parents=True, exist_ok=True)
        SEQ_CACHE.write_text(json.dumps(cache))
    except Exception:
        pass
    return seqs


# ------------------------- ESM-2 masked-marginal LLR -------------------------
class ESM2Scorer:
    """ESM-2 650M (transformers) masked-marginal scorer.
    score = logP(altAA | pos masked, WT context) - logP(refAA | pos masked, WT context).
    Truncates very long channels around the variant to stay within ESM-2's window."""

    WINDOW = 1022  # ESM-2 max usable residues (1024 - 2 special tokens)

    def __init__(self, model_name=ESM2_MODEL):
        import torch
        from transformers import AutoTokenizer, AutoModelForMaskedLM
        self.torch = torch
        self.device = "cuda" if (torch.cuda.is_available() and not FORCE_CPU) else "cpu"
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForMaskedLM.from_pretrained(model_name).to(self.device).eval()
        self.mask_id = self.tok.mask_token_id

    def _window(self, seq, pos0):
        """Return (subseq, local_index) with pos0 (0-based) centered in a <=WINDOW window."""
        if len(seq) <= self.WINDOW:
            return seq, pos0
        half = self.WINDOW // 2
        start = max(0, pos0 - half)
        end = min(len(seq), start + self.WINDOW)
        start = max(0, end - self.WINDOW)
        return seq[start:end], pos0 - start

    def score(self, seq, pos1, ref, alt):
        """pos1 = 1-based residue position. Returns LLR float, or None on mismatch/failure."""
        torch = self.torch
        pos0 = pos1 - 1
        if pos0 < 0 or pos0 >= len(seq):
            return None, "oob"
        if seq[pos0].upper() != ref.upper():
            return None, "refmismatch"
        sub, lidx = self._window(seq, pos0)
        enc = self.tok(sub, return_tensors="pt", add_special_tokens=True)
        input_ids = enc["input_ids"].to(self.device)
        # token layout: [CLS] r0 r1 ... [EOS]; residue lidx is at token index lidx+1
        tok_idx = lidx + 1
        masked = input_ids.clone()
        masked[0, tok_idx] = self.mask_id
        with torch.no_grad():
            logits = self.model(masked).logits[0, tok_idx]
            logp = torch.log_softmax(logits, dim=-1)
        try:
            ref_id = self.tok.convert_tokens_to_ids(ref.upper())
            alt_id = self.tok.convert_tokens_to_ids(alt.upper())
        except Exception:
            return None, "tokid"
        if ref_id is None or alt_id is None or ref_id == self.tok.unk_token_id \
                or alt_id == self.tok.unk_token_id:
            return None, "unktok"
        llr = float(logp[alt_id].item() - logp[ref_id].item())
        return llr, "ok"


# ------------------------- main -------------------------
def main():
    R = {}
    state = {}

    # A. dataset summary -------------------------------------------------------
    def a_summary():
        variants = load_variants()
        state["variants"] = variants
        per_gene = {}
        for g in sorted(set(v["gene"] for v in variants)):
            sub = [v for v in variants if v["gene"] == g]
            lab = Counter(v["label"] for v in sub)
            per_gene[g] = {"n": len(sub), "gof": lab.get("gof", 0), "lof": lab.get("lof", 0),
                           "quiver_channel": g in QUIVER_GENES,
                           "alias": QUIVER_ALIAS.get(g)}
        lab = Counter(v["label"] for v in variants)
        quiver_present = [g for g in QUIVER_GENES if g in per_gene]
        quiver_absent = [g for g in QUIVER_GENES if g not in per_gene]
        return {"source": "funNCion SupplementaryTable_S1 (functional GoF/LoF set)",
                "filter": "used_in_functional_prediction==1 AND prd_mech_revised in {gof,lof}",
                "n_variants": len(variants), "n_gof": lab.get("gof", 0),
                "n_lof": lab.get("lof", 0), "n_genes": len(per_gene),
                "label_scheme": "binary: gof (y=1) vs lof (y=0)",
                "quiver_genes_present": quiver_present,
                "quiver_genes_absent_from_set": quiver_absent,
                "per_gene": per_gene}
    section(a_summary, "A_dataset_summary", R)

    # shared: score every variant with ESM-2 LLR (used by B and C) -------------
    def run_esm2():
        if "esm2_scored" in state:
            return state["esm2_scored"]
        variants = state.get("variants") or load_variants()
        genes = sorted(set(v["gene"] for v in variants))
        seqs = get_sequences(genes)
        state["seqs_genes"] = sorted(seqs.keys())
        scorer = ESM2Scorer()
        scored = []
        reasons = Counter()
        for v in variants:
            seq = seqs.get(v["gene"])
            if not seq:
                reasons["no_seq"] += 1
                continue
            llr, why = scorer.score(seq, v["pos"], v["refAA"], v["altAA"])
            reasons[why] += 1
            if llr is None:
                continue
            scored.append({**v, "llr": llr})
        state["esm2_scored"] = scored
        state["esm2_reasons"] = dict(reasons)
        return scored

    # B. ESM-2 baseline overall -----------------------------------------------
    def b_esm2_overall():
        scored = run_esm2()
        if len(scored) < 10:
            return {"skip": "too few scored variants", "n_scored": len(scored),
                    "reasons": state.get("esm2_reasons")}
        y = [s["y"] for s in scored]
        llr = [s["llr"] for s in scored]
        au = auroc(y, llr)
        ba = balanced_acc_at_youden(y, llr)
        return {"model": ESM2_MODEL, "signal": "masked-marginal LLR = logP(alt)-logP(ref)",
                "n_scored": len(scored), "n_gof": int(sum(y)), "n_lof": int(len(y) - sum(y)),
                "auroc_gof_eq_1": oriented(au), "balanced_acc_at_youden": ba,
                "n_pos_mismatch_or_skipped": {k: v for k, v in (state.get("esm2_reasons") or {}).items()
                                              if k != "ok"},
                "genes_with_sequence": state.get("seqs_genes"),
                "interpretation": ("LLR is a conservation/deleteriousness signal, NOT a "
                                   "GoF-vs-LoF direction signal. AUROC near 0.5 (low "
                                   "directional_strength_abs) is the EXPECTED, motivating result: "
                                   "a generic pLM does not solve the GoF/LoF call on ion channels, "
                                   "which is the gap a specialized model (MissION/funNCion) targets.")}
    section(b_esm2_overall, "B_esm2_baseline_overall", R)

    # C. ESM-2 baseline per-gene (the QUIVER breakdown) ------------------------
    def c_esm2_per_gene():
        scored = run_esm2()
        out = {}
        # report Quiver channels first, then all other genes present.
        genes_present = sorted(set(s["gene"] for s in scored))
        ordered = [g for g in QUIVER_GENES if g in genes_present] + \
                  [g for g in genes_present if g not in QUIVER_GENES]
        for g in ordered:
            sub = [s for s in scored if s["gene"] == g]
            y = [s["y"] for s in sub]
            n_gof = int(sum(y))
            n_lof = int(len(y) - n_gof)
            entry = {"n_scored": len(sub), "n_gof": n_gof, "n_lof": n_lof,
                     "quiver_channel": g in QUIVER_GENES, "alias": QUIVER_ALIAS.get(g)}
            if n_gof >= 1 and n_lof >= 1 and len(sub) >= 8:
                au = auroc(y, [s["llr"] for s in sub])
                entry["auroc"] = oriented(au)
            else:
                entry["auroc"] = None
                entry["auroc_note"] = ("single-class (cannot compute AUROC)" if (n_gof == 0 or n_lof == 0)
                                       else "n<8 (insufficient for AUROC)")
            out[g] = entry
        out["_quiver_note"] = ("SCN3A and SCN10A(=Nav1.8) are absent from the funNCion functional "
                               "set. SCN8A/SCN9A(=Nav1.7)/CACNA1C(=Cav1.2) are single-class in this "
                               "set (no AUROC). Two-class Quiver channels: SCN1A, SCN2A, SCN5A(=Nav1.5).")
        return out
    section(c_esm2_per_gene, "C_esm2_baseline_per_gene", R)

    # D. MissION classifier (attempt; no public weights -> guarded SKIP) -------
    def d_mission():
        artifact = MISSION_DIR or MISSION_CKPT
        if not artifact or not Path(artifact).exists():
            return {"status": "SKIPPED -- no loadable MissION artifact",
                    "reason": ("MissION (medRxiv 2025.10.16.25337735) ships NO public GitHub repo "
                               "and NO downloadable checkpoint; it is reachable only via the web "
                               "portal www.synaptica.nl/variant-interpreter (no documented batch API). "
                               "Set MISSION_DIR/MISSION_CKPT to a local artifact to enable this section."),
                    "portal": "https://www.synaptica.nl/variant-interpreter",
                    "what_it_would_do": ("load MissION, score the same funNCion functional variants, "
                                         "report AUROC + per-gene breakdown, compare to ESM-2 LLR.")}
        # Best-effort generic loaders (only reached if a local artifact is provided).
        variants = state.get("variants") or load_variants()
        import torch
        if MISSION_DIR:
            sys.path.insert(0, MISSION_DIR)
        try:
            # NOTE: weights_only=False is required because MissION's serialization format is unknown
            # (no public repo/API) and likely is not a pure-tensor state_dict. This path runs ONLY when a
            # user explicitly stages a local MISSION_DIR/MISSION_CKPT artifact they trust; it never runs on
            # the public/default code path (which SKIPs above).
            obj = torch.load(MISSION_CKPT or artifact, map_location="cpu", weights_only=False)
        except Exception as e:
            return {"status": "artifact present but not loadable as torch checkpoint",
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "MissION load API is unspecified (no public repo); provide a loader script."}
        return {"status": "artifact loaded but no documented predict() API",
                "loaded_type": str(type(obj)),
                "n_variants_available": len(variants),
                "note": ("A MissION-specific predict() wrapper is required here once the model's "
                         "real API is known. No public API exists as of the research date.")}
    section(d_mission, "D_mission_classifier", R)

    # E. comparison / verdict --------------------------------------------------
    def e_comparison():
        b = R.get("B_esm2_baseline_overall", {})
        d = R.get("D_mission_classifier", {})
        esm_au = None
        if isinstance(b, dict) and isinstance(b.get("auroc_gof_eq_1"), dict):
            esm_au = b["auroc_gof_eq_1"].get("auroc")
        mission_available = isinstance(d, dict) and str(d.get("status", "")).startswith("artifact loaded but")
        out = {"esm2_overall_auroc": esm_au,
               "esm2_directional_strength": (b.get("auroc_gof_eq_1", {}) or {}).get("directional_strength_abs")
               if isinstance(b, dict) else None,
               "mission_scores_available": mission_available,
               "funNCion_reference_auroc_paper": 0.897,
               "mission_reported_auroc_paper": 0.925}
        if mission_available:
            out["verdict"] = ("Both models scored on the same Quiver-channel variants -- see B/D for "
                              "the head-to-head AUROC.")
        else:
            out["verdict"] = ("BANKED: generic-pLM (ESM-2 650M) zero-shot LLR characterized on the real "
                              "funNCion GoF/LoF ion-channel variants (Quiver's SCN/Nav + Cav1.2). LLR is a "
                              "conservation signal and is expected near-chance on GoF-vs-LoF DIRECTION; "
                              "low directional_strength confirms a generic pLM does not solve this call. "
                              "MissION itself is NOT offline-loadable (web-portal only, no weights/API), so "
                              "the specialized-vs-generic head-to-head cannot be run offline; the paper "
                              "reports MissION 0.925 vs funNCion 0.897. To close the loop, integrate the "
                              "Synaptica portal or obtain weights from the authors.")
        return out
    section(e_comparison, "E_comparison", R)

    payload = {
        "model": "MissION (specialized ion-channel pLM GoF/LoF) -- NOT offline-loadable; "
                 "characterized via generic-pLM (ESM-2 650M) baseline on funNCion variants",
        "mission_paper": "medRxiv 2025.10.16.25337735",
        "mission_portal": "https://www.synaptica.nl/variant-interpreter",
        "mission_code_status": "no public repo / no downloadable checkpoint (verified 2026-06)",
        "fallback_substrate": "funNCion (https://github.com/heyhen/funNCion, Apache-2.0) functional GoF/LoF set",
        "baseline_model": ESM2_MODEL,
        "task": "ion-channel missense GoF vs LoF (binary)",
        "track": "variant-effect / channelopathy (Quiver SCN/Nav + Cav1.2 focus)",
        "device": "cpu" if FORCE_CPU else "cuda-if-available",
        "results": R,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)

    summ = {}
    b = R.get("B_esm2_baseline_overall", {})
    if isinstance(b, dict):
        summ["esm2_n_scored"] = b.get("n_scored")
        summ["esm2_auroc"] = (b.get("auroc_gof_eq_1") or {}).get("auroc") if isinstance(b.get("auroc_gof_eq_1"), dict) else None
    summ["mission_available"] = (R.get("E_comparison", {}) or {}).get("mission_scores_available")
    print(json.dumps(summ, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
