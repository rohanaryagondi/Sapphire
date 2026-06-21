"""Nav/Cav ion-channel variant-effect FINE-TUNE: supervised GoF-vs-LoF classifier (Track 9).

GOAL
----
Track-9 (variant effect / channelopathy direction). A *generic* protein-LM signal --
ESM-2-650M masked-marginal LLR -- scores only AUROC ~0.665 on Gain-of-Function vs
Loss-of-Function: it captures deleteriousness, NOT direction (see
results/mission_characterization.md). funNCion (a channel-specialized model) hits 0.897;
MissION reports 0.925. This run trains a SUPERVISED GoF/LoF classifier on the pooled
SCION + funNCion Nav/Cav variant corpus on top of ESM-2-650M features and asks:

  (1) does the supervised model BEAT the generic ESM-2 LLR baseline (~0.665) and approach
      funNCion (0.897) under a leave-one-GENE-out (GroupKFold) split -- i.e. does it
      generalize across the Nav/Cav family rather than memorize a gene?
  (2) does cross-channel training TRANSFER to held-out Nav1.8/SCN10A -- train on ALL
      non-SCN10A variants, test on the 16 SCN10A variants (the concrete Nav1.8
      variant-model proof; n=16 small, reported with that caveat).

SCN10A/Nav1.8 was thought to have NO public functional labels; SCION supplies 16 SCN10A
variants WITH GoF/LoF direction (9 GOF / 7 LOF), which is what makes the transfer test
possible at all.

============================ DATA (verified on-laptop) ============================
SCION   data/cns_variants/scion/clean_tbl.csv  (staged to s3 by the launcher)
        columns: id, gene, y (GOF/LOF), pheno, aa1 (ref AA, 1-letter), aa2 (alt AA, 1-letter), pos
        375 NaV variants (164 GOF / 211 LOF); SCN10A = 16 (9 GOF / 7 LOF). 1-letter AA codes.
        Genes: SCN5A SCN1A SCN9A SCN2A SCN4A SCN8A SCN10A SCN3A SCN11A.
funNCion data/cns_variants/funncion/S1_pathogenic_GoF_LoF_labels.txt  (TAB-sep, latin-1)
        columns incl.: gene, pos, refAA, altAA, prd_mech_revised (gof/lof/unknown/na).
        Keep ONLY rows labelled gof/lof with 1-letter AA + integer pos -> 2,771 usable.
        Genes: SCN1A/2A/4A/5A/8A/9A + CACNA1A/C/D/E/F/S. (SCN10A/3A/11A NOT present here.)

MERGE   into ONE (gene, pos, refAA, altAA, label in {GOF,LOF}) table:
        - normalize AA codes to 1-letter uppercase; normalize labels to GOF/LOF uppercase;
        - dedupe by (gene, pos, refAA, altAA); SCION WINS on a label conflict.

FEATURES (per variant, on the gene's UniProt canonical WT sequence)
  * ESM-2-650M masked-marginal LLR at the variant position (the baseline signal), AND
  * ESM-2-650M per-residue embedding at the variant position for the WINDOWED (+/-64 aa)
    WT and MUTANT sequences, plus their difference (wt || mut-minus-wt) -- the supervised
    representation. (Per-residue at the variant gives a local, position-specific feature;
    pooling the +/-64 window keeps it within ESM-2's context.)
  * aux: normalized position (pos/len), refAA & altAA one-hot (20+X each), gene one-hot.

CLASSIFIER  sklearn GradientBoostingClassifier (robust on ~3k rows, no GPU tuning needed),
            standardized features. P(GOF) is the score.

BASELINE    the raw ESM-2 LLR alone (oriented AUROC + balanced-acc at Youden-J) -- reproduces
            the ~0.665 generic reference, the number the supervised model must beat.

REFERENCES (for the JSON headline): generic ESM-2 LLR 0.665, funNCion 0.897, MissION 0.925.

SUCCESS: supervised group-by-gene AUROC > generic LLR baseline (~0.665) AND held-out
         Nav1.8/SCN10A AUROC clearly above chance (>0.5, ideally approaching the family
         number) -- that is the cross-channel-transfer-to-Nav1.8 proof.

UniProt fetch + LLR computation + the gene->UniProt accession map are REUSED from
aws/mission_eval.py (GENE_UNIPROT, fetch_uniprot_seq pattern, ESM2 masked-marginal LLR).
USE_TF=0 / USE_FLAX=0 set below; runs on CUDA if available.
==================================================================================
"""
from __future__ import annotations

import os

os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("USE_FLAX", "0")

import csv
import json
import socket
import sys
import traceback
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np

# socket timeout so a stalled UniProt fetch cannot hang the whole run
socket.setdefaulttimeout(int(os.environ.get("NET_TIMEOUT", "60")))

OUT = Path(os.environ.get("OUT", "/root/variant_finetune_out/variant_finetune_result.json"))
SCION_CSV = os.environ.get("SCION_CSV", "/opt/data/scion_clean_tbl.csv")
FUNNCION_TSV = os.environ.get(
    "FUNNCION_TSV", "/opt/data/funncion_S1_pathogenic_GoF_LoF_labels.txt"
)
ESM2_MODEL = os.environ.get("ESM2_MODEL", "facebook/esm2_t33_650M_UR50D")
FORCE_CPU = os.environ.get("FORCE_CPU") == "1"
MAX_VARIANTS = int(os.environ.get("MAX_VARIANTS", "0"))  # 0 = no cap
WINDOW_HALF = int(os.environ.get("WINDOW_HALF", "64"))   # +/- residues around variant
SEED = int(os.environ.get("SEED", "0"))
SEQ_CACHE = Path(os.environ.get("SEQ_CACHE", "/root/variant_finetune_out/uniprot_seqs.json"))

# ---- gene -> canonical human UniProt accession (REUSED from aws/mission_eval.py) ----
GENE_UNIPROT = {
    "SCN1A": "P35498", "SCN2A": "Q99250", "SCN3A": "Q9NY46", "SCN4A": "P35499",
    "SCN5A": "Q14524", "SCN8A": "Q9UQD0", "SCN9A": "Q15858", "SCN10A": "Q9Y5Y9",
    "SCN11A": "Q9UI33",
    "CACNA1A": "O00555", "CACNA1B": "Q00975", "CACNA1C": "Q13936", "CACNA1D": "Q01668",
    "CACNA1E": "Q15878", "CACNA1F": "O60840", "CACNA1G": "O43497", "CACNA1H": "O95180",
    "CACNA1I": "Q9P0X4", "CACNA1S": "Q13698",
}
QUIVER_ALIAS = {
    "SCN9A": "Nav1.7", "SCN10A": "Nav1.8", "SCN5A": "Nav1.5", "SCN1A": "Nav1.1",
    "SCN2A": "Nav1.2", "SCN3A": "Nav1.3", "SCN8A": "Nav1.6", "SCN11A": "Nav1.9",
    "SCN4A": "Nav1.4", "CACNA1C": "Cav1.2", "CACNA1A": "Cav2.1", "CACNA1S": "Cav1.1",
    "CACNA1D": "Cav1.3", "CACNA1E": "Cav2.3", "CACNA1F": "Cav1.4",
}
AA_ALPHABET = list("ACDEFGHIKLMNPQRSTVWY")  # 20 standard; X bucket for anything else
NAV18_GENE = "SCN10A"


# ------------------------- self-contained metrics (no sklearn dep needed) -------------------------
def auroc(y, s):
    """Tie-correct (mid-rank) Mann-Whitney AUROC; y in {0,1}, s=score. None if degenerate."""
    y = np.asarray(y)
    s = np.asarray(s, float)
    p = int((y == 1).sum())
    n = int((y == 0).sum())
    if p == 0 or n == 0 or len(y) < 3:
        return None
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    start = 0
    midrank = {}
    for k, c in enumerate(cnt):
        midrank[k] = (start + 1 + start + c) / 2.0
        start += c
    rb = np.array([midrank[i] for i in inv])
    return float((rb[y == 1].sum() - p * (p + 1) / 2.0) / (p * n))


def balanced_acc_at_youden(y, s):
    """Threshold maximizing Youden's J on s (higher s -> predict y=1); bal-acc + thr + sens/spec."""
    y = np.asarray(y)
    s = np.asarray(s, float)
    p = int((y == 1).sum())
    n = int((y == 0).sum())
    if p == 0 or n == 0:
        return None
    best = None
    for t in np.unique(s):
        pred = (s >= t).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        tn = int(((pred == 0) & (y == 0)).sum())
        sens = tp / p
        spec = tn / n
        j = sens + spec - 1.0
        if best is None or j > best["youden_j"]:
            best = {"threshold": float(t), "sensitivity": round(sens, 4),
                    "specificity": round(spec, 4),
                    "balanced_acc": round((sens + spec) / 2.0, 4),
                    "youden_j": round(j, 4)}
    return best


def oriented(au):
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
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:1500]}", flush=True)


# ------------------------- variant loaders + merge -------------------------
def _norm_aa(a):
    a = (a or "").strip().upper()
    return a if len(a) == 1 else ""


def load_scion(path):
    """SCION clean_tbl.csv -> list of {gene,pos,refAA,altAA,label,source}. aa1=ref aa2=alt (1-letter)."""
    out = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            ref = _norm_aa(r.get("aa1"))
            alt = _norm_aa(r.get("aa2"))
            lab = (r.get("y") or "").strip().upper()
            if lab not in ("GOF", "LOF") or not ref or not alt:
                continue
            try:
                pos = int(str(r.get("pos")).strip())
            except (ValueError, TypeError):
                continue
            gene = (r.get("gene") or "").strip()
            if not gene:
                continue
            out.append({"gene": gene, "pos": pos, "refAA": ref, "altAA": alt,
                        "label": lab, "source": "scion"})
    return out


def load_funncion(path):
    """funNCion S1 (TAB, latin-1) -> rows with prd_mech_revised in {gof,lof}, 1-letter AA, int pos."""
    raw = Path(path).read_text(encoding="latin-1").splitlines()
    if not raw:
        return []
    header = raw[0].split("\t")
    idx = {h: i for i, h in enumerate(header)}
    for col in ("gene", "pos", "refAA", "altAA", "prd_mech_revised"):
        if col not in idx:
            raise KeyError(f"funNCion missing column {col!r}; header={header}")
    out = []
    for ln in raw[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) < len(header):
            continue
        mech = f[idx["prd_mech_revised"]].strip().lower()
        if mech not in ("gof", "lof"):
            continue
        ref = _norm_aa(f[idx["refAA"]])
        alt = _norm_aa(f[idx["altAA"]])
        if not ref or not alt:
            continue
        try:
            pos = int(f[idx["pos"]].strip())
        except ValueError:
            continue
        gene = f[idx["gene"]].strip()
        if not gene:
            continue
        out.append({"gene": gene, "pos": pos, "refAA": ref, "altAA": alt,
                    "label": mech.upper(), "source": "funncion"})
    return out


def merge_variants():
    """Merge SCION + funNCion; dedupe by (gene,pos,refAA,altAA); SCION wins on label conflict.
    Returns (merged_list, merge_stats)."""
    scion = load_scion(SCION_CSV)
    fun = load_funncion(FUNNCION_TSV)
    merged = {}
    conflicts = 0
    # SCION first so it owns the key; mark scion keys to detect conflicts when funNCion arrives.
    for v in scion:
        merged[(v["gene"], v["pos"], v["refAA"], v["altAA"])] = v
    n_dup_fun = 0
    for v in fun:
        k = (v["gene"], v["pos"], v["refAA"], v["altAA"])
        if k in merged:
            n_dup_fun += 1
            if merged[k]["label"] != v["label"]:
                conflicts += 1  # SCION already in place -> SCION wins, keep it
            continue
        merged[k] = v
    out = sorted(merged.values(), key=lambda v: (v["gene"], v["pos"], v["refAA"], v["altAA"]))
    for i, v in enumerate(out):
        v["protid"] = f"{v['gene']}:{v['pos']}:{v['refAA']}:{v['altAA']}"
        v["y"] = 1 if v["label"] == "GOF" else 0
    if MAX_VARIANTS and len(out) > MAX_VARIANTS:
        out = out[:MAX_VARIANTS]
    stats = {"n_scion_raw": len(scion), "n_funncion_raw": len(fun),
             "n_funncion_dup_with_scion": n_dup_fun, "n_label_conflicts_scion_won": conflicts,
             "n_merged": len(out)}
    return out, stats


# ------------------------- UniProt WT-sequence fetch (REUSED from mission_eval) -------------------------
def fetch_uniprot_seq(acc):
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers={"User-Agent": "variant-finetune/1.0"})
    with urllib.request.urlopen(req, timeout=socket.getdefaulttimeout() or 60) as r:
        fasta = r.read().decode("utf-8")
    return "".join(l.strip() for l in fasta.splitlines() if not l.startswith(">"))


def get_sequences(genes):
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
            print(f"[warn] no UniProt accession for gene {g}", flush=True)
            continue
        try:
            s = fetch_uniprot_seq(acc)
            if s:
                seqs[g] = cache[g] = s
                print(f"[seq] {g}/{acc} len={len(s)}", flush=True)
        except Exception as e:
            print(f"[warn] UniProt fetch {g}/{acc} failed: {e}", flush=True)
    try:
        SEQ_CACHE.parent.mkdir(parents=True, exist_ok=True)
        SEQ_CACHE.write_text(json.dumps(cache))
    except Exception:
        pass
    return seqs


# ------------------------- ESM-2 LLR + per-residue embedding featurizer -------------------------
class ESM2Featurizer:
    """ESM-2 650M (transformers): masked-marginal LLR + per-residue embedding at a variant.

    LLR  = logP(altAA | pos masked, WT context) - logP(refAA | pos masked, WT context).
    EMB  = last-hidden-state vector AT the variant residue for the windowed WT and MUT
           sequences (variant residue substituted in the MUT pass). Window = +/-WINDOW_HALF.
    """

    def __init__(self, model_name=ESM2_MODEL):
        import torch
        from transformers import AutoTokenizer, AutoModelForMaskedLM
        self.torch = torch
        self.device = "cuda" if (torch.cuda.is_available() and not FORCE_CPU) else "cpu"
        self.tok = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForMaskedLM.from_pretrained(model_name).to(self.device).eval()
        self.mask_id = self.tok.mask_token_id

    def _window(self, seq, pos0):
        """Return (subseq, local_index) with pos0 (0-based) centered in a (2*WINDOW_HALF+1) window,
        clamped so it never exceeds ESM-2's usable context (1022)."""
        max_win = 1022
        win = min(2 * WINDOW_HALF + 1, max_win)
        half = win // 2
        start = max(0, pos0 - half)
        end = min(len(seq), start + win)
        start = max(0, end - win)
        return seq[start:end], pos0 - start

    def featurize(self, seq, pos1, ref, alt):
        """Returns (llr:float, wt_emb:np.ndarray, mut_emb:np.ndarray, reason:str) or (None,...,why)."""
        torch = self.torch
        pos0 = pos1 - 1
        if pos0 < 0 or pos0 >= len(seq):
            return None, None, None, "oob"
        if seq[pos0].upper() != ref.upper():
            return None, None, None, "refmismatch"
        sub, lidx = self._window(seq, pos0)
        ref_id = self.tok.convert_tokens_to_ids(ref.upper())
        alt_id = self.tok.convert_tokens_to_ids(alt.upper())
        unk = self.tok.unk_token_id
        if ref_id is None or alt_id is None or ref_id == unk or alt_id == unk:
            return None, None, None, "unktok"

        enc = self.tok(sub, return_tensors="pt", add_special_tokens=True)
        input_ids = enc["input_ids"].to(self.device)
        tok_idx = lidx + 1  # [CLS] r0 r1 ... [EOS]; residue lidx -> token lidx+1

        with torch.no_grad():
            # masked-marginal LLR (mask the variant position)
            masked = input_ids.clone()
            masked[0, tok_idx] = self.mask_id
            mlm = self.model(masked, output_hidden_states=False)
            logp = torch.log_softmax(mlm.logits[0, tok_idx], dim=-1)
            llr = float(logp[alt_id].item() - logp[ref_id].item())

            # WT per-residue embedding at the variant position
            wt_out = self.model(input_ids, output_hidden_states=True)
            wt_emb = wt_out.hidden_states[-1][0, tok_idx].float().cpu().numpy()

            # MUT per-residue embedding (substitute alt at the variant token)
            mut_ids = input_ids.clone()
            mut_ids[0, tok_idx] = alt_id
            mut_out = self.model(mut_ids, output_hidden_states=True)
            mut_emb = mut_out.hidden_states[-1][0, tok_idx].float().cpu().numpy()

        return llr, wt_emb, mut_emb, "ok"


# ------------------------- aux feature encoders -------------------------
def aa_onehot(a):
    v = np.zeros(len(AA_ALPHABET) + 1, dtype=np.float32)
    a = (a or "").upper()
    if a in AA_ALPHABET:
        v[AA_ALPHABET.index(a)] = 1.0
    else:
        v[-1] = 1.0  # X bucket
    return v


def build_feature_matrix(scored, seqs, genes_sorted):
    """Assemble per-variant feature rows. Returns (X, y, groups, llr_only, kept_indices)."""
    gene_index = {g: i for i, g in enumerate(genes_sorted)}
    X, y, groups, llr_only = [], [], [], []
    for s in scored:
        seqlen = max(1, len(seqs.get(s["gene"], "")))
        emb_wt = s["wt_emb"]
        emb_mut = s["mut_emb"]
        emb_diff = emb_mut - emb_wt
        gene_oh = np.zeros(len(genes_sorted), dtype=np.float32)
        gene_oh[gene_index[s["gene"]]] = 1.0
        pos_norm = np.array([s["pos"] / seqlen], dtype=np.float32)
        feat = np.concatenate([
            np.array([s["llr"]], dtype=np.float32),    # baseline LLR signal
            emb_wt.astype(np.float32),                  # WT residue embedding
            emb_diff.astype(np.float32),                # mut-minus-wt residue embedding
            aa_onehot(s["refAA"]),
            aa_onehot(s["altAA"]),
            pos_norm,
            gene_oh,
        ])
        X.append(feat)
        y.append(s["y"])
        groups.append(s["gene"])
        llr_only.append(s["llr"])
    return (np.vstack(X), np.asarray(y, int), np.asarray(groups),
            np.asarray(llr_only, float))


# ------------------------- classifier helpers -------------------------
def make_clf():
    from sklearn.ensemble import GradientBoostingClassifier
    return GradientBoostingClassifier(random_state=SEED)


def fit_predict_proba(Xtr, ytr, Xte):
    """Standardize on train, fit GBT, return P(GOF=1) for Xte."""
    from sklearn.preprocessing import StandardScaler
    sc = StandardScaler().fit(Xtr)
    clf = make_clf()
    clf.fit(sc.transform(Xtr), ytr)
    return clf.predict_proba(sc.transform(Xte))[:, 1]


# ------------------------- main -------------------------
def main():
    R = {}
    state = {}

    # A. merge + corpus summary -----------------------------------------------
    def a_corpus():
        merged, mstats = merge_variants()
        state["merged"] = merged
        per_gene = {}
        for g in sorted(set(v["gene"] for v in merged)):
            sub = [v for v in merged if v["gene"] == g]
            lab = Counter(v["label"] for v in sub)
            src = Counter(v["source"] for v in sub)
            per_gene[g] = {"n": len(sub), "gof": lab.get("GOF", 0), "lof": lab.get("LOF", 0),
                           "alias": QUIVER_ALIAS.get(g), "from_scion": src.get("scion", 0),
                           "from_funncion": src.get("funncion", 0)}
        lab = Counter(v["label"] for v in merged)
        scn10 = [v for v in merged if v["gene"] == NAV18_GENE]
        scn10_lab = Counter(v["label"] for v in scn10)
        return {"sources": {"scion": "data/cns_variants/scion/clean_tbl.csv",
                            "funncion": "data/cns_variants/funncion/S1_pathogenic_GoF_LoF_labels.txt"},
                "merge": mstats,
                "n_variants": len(merged), "n_gof": lab.get("GOF", 0), "n_lof": lab.get("LOF", 0),
                "n_genes": len(per_gene),
                "label_scheme": "binary: GOF (y=1) vs LOF (y=0)",
                "nav1_8_scn10a": {"n": len(scn10), "gof": scn10_lab.get("GOF", 0),
                                  "lof": scn10_lab.get("LOF", 0),
                                  "note": "the held-out cross-channel-transfer test set (small n)"},
                "per_gene": per_gene}
    section(a_corpus, "A_corpus_summary", R)

    # shared: featurize every variant with ESM-2 (LLR + WT/MUT residue embeddings) ----
    def run_featurize():
        if "scored" in state:
            return state["scored"]
        merged = state.get("merged")
        if merged is None:
            merged, _ = merge_variants()
            state["merged"] = merged
        genes = sorted(set(v["gene"] for v in merged))
        seqs = get_sequences(genes)
        state["seqs"] = seqs
        state["seqs_genes"] = sorted(seqs.keys())
        feat = ESM2Featurizer()
        scored = []
        reasons = Counter()
        for i, v in enumerate(merged):
            seq = seqs.get(v["gene"])
            if not seq:
                reasons["no_seq"] += 1
                continue
            llr, wt_emb, mut_emb, why = feat.featurize(seq, v["pos"], v["refAA"], v["altAA"])
            reasons[why] += 1
            if llr is None:
                continue
            scored.append({**v, "llr": llr, "wt_emb": wt_emb, "mut_emb": mut_emb})
            if (i + 1) % 200 == 0:
                print(f"[featurize] {i + 1}/{len(merged)} scored={len(scored)}", flush=True)
        state["scored"] = scored
        state["feat_reasons"] = dict(reasons)
        print(f"[featurize] done scored={len(scored)} reasons={dict(reasons)}", flush=True)
        return scored

    # B. generic ESM-2 LLR baseline (the ~0.665 reference to beat) -------------
    def b_llr_baseline():
        scored = run_featurize()
        if len(scored) < 10:
            return {"skip": "too few featurized variants", "n": len(scored),
                    "reasons": state.get("feat_reasons")}
        y = [s["y"] for s in scored]
        llr = [s["llr"] for s in scored]
        return {"model": ESM2_MODEL, "signal": "masked-marginal LLR = logP(alt)-logP(ref)",
                "n_scored": len(scored), "n_gof": int(sum(y)), "n_lof": int(len(y) - sum(y)),
                "auroc_gof_eq_1": oriented(auroc(y, llr)),
                "balanced_acc_at_youden": balanced_acc_at_youden(y, llr),
                "skipped_reasons": {k: v for k, v in (state.get("feat_reasons") or {}).items()
                                    if k != "ok"},
                "genes_with_sequence": state.get("seqs_genes"),
                "reference_generic_llr_auroc": 0.665,
                "interpretation": ("Generic ESM-2 LLR is a conservation/deleteriousness signal, "
                                   "not a GoF-vs-LoF DIRECTION signal; ~0.665 is the bar the "
                                   "supervised model must clear.")}
    section(b_llr_baseline, "B_esm2_llr_baseline", R)

    # C. SUPERVISED eval (1): GroupKFold by GENE (does it generalize across the family?) ----
    def c_supervised_groupkfold():
        from sklearn.model_selection import GroupKFold
        scored = run_featurize()
        if len(scored) < 30:
            return {"skip": "too few featurized variants for CV", "n": len(scored)}
        genes_sorted = sorted(set(s["gene"] for s in scored))
        X, y, groups, llr_only = build_feature_matrix(scored, state["seqs"], genes_sorted)
        state["matrix"] = (X, y, groups, llr_only, scored, genes_sorted)
        n_groups = len(set(groups))
        n_splits = min(n_groups, int(os.environ.get("N_SPLITS", "5")))
        if n_splits < 2:
            return {"skip": "need >=2 gene groups", "n_groups": n_groups}
        gkf = GroupKFold(n_splits=n_splits)
        oof_pred = np.full(len(y), np.nan)
        oof_llr = np.array(llr_only, float)
        for tr, te in gkf.split(X, y, groups):
            if len(set(y[tr])) < 2:
                continue  # a fold whose train side is single-class can't fit
            oof_pred[te] = fit_predict_proba(X[tr], y[tr], X[te])
        mask = ~np.isnan(oof_pred)
        sup_au = auroc(y[mask], oof_pred[mask])
        sup_ba = balanced_acc_at_youden(y[mask], oof_pred[mask])
        base_au = auroc(y[mask], oof_llr[mask])  # LLR on the same scored rows, for apples-to-apples
        # per-gene held-out AUROC (gene appears only in its own test fold under GroupKFold)
        per_gene = {}
        for g in genes_sorted:
            gi = (groups == g) & mask
            yy = y[gi]
            pp = oof_pred[gi]
            n_gof = int((yy == 1).sum())
            n_lof = int((yy == 0).sum())
            entry = {"n": int(gi.sum()), "gof": n_gof, "lof": n_lof,
                     "alias": QUIVER_ALIAS.get(g)}
            if n_gof >= 1 and n_lof >= 1 and gi.sum() >= 8:
                entry["auroc"] = oriented(auroc(yy, pp))
            else:
                entry["auroc"] = None
                entry["auroc_note"] = ("single-class in test fold"
                                       if (n_gof == 0 or n_lof == 0) else "n<8")
            per_gene[g] = entry
        return {"protocol": "leave-one-GENE-out via GroupKFold (gene = group)",
                "classifier": "GradientBoostingClassifier on [LLR | WT-emb | (mut-wt)-emb | "
                              "refAA-1hot | altAA-1hot | pos/len | gene-1hot], StandardScaler",
                "n_splits": n_splits, "n_eval": int(mask.sum()),
                "feature_dim": int(X.shape[1]),
                "supervised_auroc": oriented(sup_au),
                "supervised_balanced_acc_at_youden": sup_ba,
                "esm2_llr_baseline_auroc_same_rows": oriented(base_au),
                "beats_generic_llr": (sup_au is not None and base_au is not None
                                      and sup_au > base_au),
                "per_gene_heldout": per_gene}
    section(c_supervised_groupkfold, "C_supervised_groupkfold_by_gene", R)

    # D. SUPERVISED eval (2): HELD-OUT Nav1.8/SCN10A transfer ------------------
    def d_heldout_nav18():
        scored = run_featurize()
        cached = state.get("matrix")
        if cached is not None:
            X, y, groups, llr_only, _, genes_sorted = cached
        else:
            genes_sorted = sorted(set(s["gene"] for s in scored))
            X, y, groups, llr_only = build_feature_matrix(scored, state["seqs"], genes_sorted)
        is_nav = groups == NAV18_GENE
        n_test = int(is_nav.sum())
        if n_test < 3:
            return {"skip": f"too few {NAV18_GENE} variants featurized", "n_scn10a": n_test,
                    "note": ("SCN10A is absent from funNCion's gof/lof set; it comes only from "
                             "SCION. If 0, check the SCN10A UniProt sequence / refAA matches.")}
        tr = ~is_nav
        if len(set(y[tr])) < 2:
            return {"skip": "training side single-class", "n_scn10a": n_test}
        pred = fit_predict_proba(X[tr], y[tr], X[is_nav])
        yt = y[is_nav]
        au = auroc(yt, pred)
        ba = balanced_acc_at_youden(yt, pred)
        base_au = auroc(yt, np.asarray(llr_only)[is_nav])
        return {"protocol": f"train on ALL non-{NAV18_GENE} variants, test on the "
                            f"{n_test} {NAV18_GENE}/Nav1.8 variants (cross-channel transfer)",
                "n_train": int(tr.sum()), "n_test_scn10a": n_test,
                "n_test_gof": int((yt == 1).sum()), "n_test_lof": int((yt == 0).sum()),
                "supervised_auroc": oriented(au),
                "supervised_balanced_acc_at_youden": ba,
                "esm2_llr_baseline_auroc_on_scn10a": oriented(base_au),
                "beats_generic_llr": (au is not None and base_au is not None and au > base_au),
                "caveat": f"n={n_test} is small; AUROC has wide CI -- read as directional evidence."}
    section(d_heldout_nav18, "D_heldout_nav1_8_transfer", R)

    # E. verdict / headline ----------------------------------------------------
    def e_verdict():
        base = (R.get("B_esm2_llr_baseline", {}) or {}).get("auroc_gof_eq_1") or {}
        base_au = base.get("auroc") if isinstance(base, dict) else None
        c = R.get("C_supervised_groupkfold_by_gene", {}) or {}
        sup_fam = (c.get("supervised_auroc") or {}).get("auroc") if isinstance(c.get("supervised_auroc"), dict) else None
        d = R.get("D_heldout_nav1_8_transfer", {}) or {}
        sup_nav = (d.get("supervised_auroc") or {}).get("auroc") if isinstance(d.get("supervised_auroc"), dict) else None
        beats_family = (sup_fam is not None and base_au is not None and sup_fam > base_au)
        transfers = (sup_nav is not None and sup_nav > 0.5)
        return {"references": {"generic_esm2_llr_auroc": 0.665, "funNCion_auroc": 0.897,
                               "mission_auroc": 0.925},
                "esm2_llr_baseline_auroc": base_au,
                "supervised_family_groupkfold_auroc": sup_fam,
                "supervised_heldout_nav1_8_auroc": sup_nav,
                "Q1_beats_generic_llr_across_family": beats_family,
                "Q2_transfers_to_heldout_nav1_8": transfers,
                "success_criterion": ("Q1: supervised family AUROC > generic LLR (~0.665); "
                                      "Q2: held-out SCN10A/Nav1.8 AUROC clearly > 0.5 "
                                      "(ideally approaching the family number)."),
                "headline": (f"Supervised GoF/LoF on pooled SCION+funNCion Nav/Cav variants: "
                             f"family-generalization AUROC={sup_fam} (vs generic LLR {base_au}; "
                             f"funNCion 0.897); held-out Nav1.8/SCN10A transfer AUROC={sup_nav}. "
                             f"Beats generic LLR across family: {beats_family}; "
                             f"transfers to Nav1.8: {transfers}.")}
    section(e_verdict, "E_verdict", R)

    payload = {
        "model": "Supervised GoF/LoF classifier (GradientBoosting) on ESM-2-650M features "
                 "(masked-marginal LLR + WT/MUT residue embeddings) over pooled SCION+funNCion "
                 "Nav/Cav variants",
        "baseline_model": ESM2_MODEL,
        "task": "ion-channel missense GoF vs LoF (binary, directional)",
        "track": "Track 9 -- variant effect / channelopathy (Nav/Cav family; held-out Nav1.8 transfer)",
        "data": {"scion": "data/cns_variants/scion/clean_tbl.csv (375 NaV; SCN10A=16)",
                 "funncion": "S1_pathogenic_GoF_LoF_labels.txt (2,771 gof/lof; no SCN10A)"},
        "references": {"generic_esm2_llr": 0.665, "funNCion": 0.897, "mission": 0.925},
        "window_half": WINDOW_HALF, "seed": SEED,
        "device": "cpu" if FORCE_CPU else "cuda-if-available",
        "results": R,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)

    summ = {
        "n_merged": (R.get("A_corpus_summary", {}) or {}).get("n_variants"),
        "n_scn10a": ((R.get("A_corpus_summary", {}) or {}).get("nav1_8_scn10a") or {}).get("n"),
        "esm2_llr_auroc": ((R.get("B_esm2_llr_baseline", {}) or {}).get("auroc_gof_eq_1") or {}).get("auroc"),
        "supervised_family_auroc": ((R.get("C_supervised_groupkfold_by_gene", {}) or {}).get("supervised_auroc") or {}).get("auroc"),
        "supervised_nav1_8_auroc": ((R.get("D_heldout_nav1_8_transfer", {}) or {}).get("supervised_auroc") or {}).get("auroc"),
    }
    print(json.dumps(summ, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
