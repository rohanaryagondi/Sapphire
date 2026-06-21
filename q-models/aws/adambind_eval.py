"""AdaMBind few-shot (MAML) DTI characterization — Track 2/3 head-to-head (overnight, unattended).

WHY (docs/model_scout_2026-06-14.md #3): AdaMBind is MAML few-shot drug-target affinity, cold-start
BY DESIGN (sequence + SMILES, no pretrained PLM / no 3D structure) — the closest external prior-art to
the planned Quiver Nav fine-tune. Question: does *few-shot meta-adaptation* beat zero-shot on our
cold targets (Nav1.8 n=11, mTOR n=7), and how does it stack vs BALM (0.857/1.000) and Boltz-2 (0.714/1.000)?

================================  VERIFIED REPO API  ================================
Repo:    https://github.com/Moohyun-w/AdaMBind  (commit 01a169a; paper: Nat. Commun. s41467-026-70554-5)
License: NO LICENSE FILE in repo (=> "all rights reserved" by default) — EVAL / RESEARCH ONLY, do not ship.
Weights: NONE shipped. AdaMBind meta-TRAINS from scratch on Davis/KIBA/BindingDB. We meta-train a small
         base learner on-instance from a PyTDC base set (BindingDB_Kd), then do the k-shot adaptation.

Model (model/gat_gcn.py, the train.py default `--gnn gat_gcn`):
  class GAT_GCN(MessagePassing): def __init__(self, **kwargs)   # functional-weight net; vars=nn.ParameterList
  forward(self, data, vars=None) -> xc  (continuous affinity, shape [B,1]; HIGHER = stronger binding)
  Drug  = PyG molecular graph, 78-dim atom features (44 symbol + 11 degree + 11 numH + 11 implicit-val + 1 arom).
  Prot  = integer-encoded seq, embedding table size 26, conv1d in_channels=1000 => SEQUENCE LENGTH MUST BE 1000.

Feature extraction (create_data.py — reused verbatim, imported, NOT reimplemented):
  smile_to_graph(smile) -> (c_size, features, edge_index)
  seq_voc = "ABCDEFGHIKLMNOPQRSTUVWXYZ"; seq_dict = {v:(i+1)}; max_seq_len = 1000; seq_cat(prot) -> np.array(1000,)

Dataset (utils/TestbedDataset.py):
  TestbedDataset(root, dataset, xd=<smiles list>, xt=<list of seq_cat arrays>, y=<affinity list>, smile_graph=<dict>)
  Builds PyG Data(x=features, edge_index, y=FloatTensor([label]), target=LongTensor([seq_cat_array])).

MAML trainer (model/Trainer.py) — the EXACT adaptation + predict calls from train.py:
  trainer = Trainer(net)                              # snapshots net.state_dict() as init_params
  fast_weights = trainer.train(net, args, it, [TASK], F_data, update=0)   # INNER-loop adapt on F_data[TASK][0]
  preds, labels = trainer.predict(net, args, [TASK], F_data, fast_weights, ct=False)  # adapt on [0], predict [1]
  F_data structure (utils/DataSplit.train_datasplit): { target_seq : [support_list, query_list] } of PyG Data.
  Inner LR args.reg_lr=1e-4, update_step_train=5, update_step_test=3; outer args.meta_lr=1e-5. Loss = MSE.
  predict() ranks by regressed affinity; we take the predicted value as the binder score (higher=binder).

EVAL DESIGN (all sections guarded; one failure still banks the rest):
  M. Meta-train GAT_GCN on a PyTDC BindingDB_Kd base set (proteins != our panels), banking init weights.
  A. ZERO-shot binder-vs-decoy AUROC per target: score panel compounds with the meta-init net (NO target adapt).
  B. FEW-shot (k=5): support = 5 labeled panel pairs (stratified binder/decoy), query = the rest; adapt + AUROC.
     Repeated over N random support draws (mean ± sd) — the core AdaMBind claim: does adaptation help cold targets?
  C. Per-compound zero-shot scores for the head-to-head table (vs BALM / Boltz columns already in panels).
Binary panels -> pseudo-affinity for the regressor: binder=BIND_HI (8.0), decoy=BIND_LO (4.0) (pKd-scale, like Davis).
"""
from __future__ import annotations
import json, os, sys, types, importlib.util, traceback, random
from pathlib import Path
import numpy as np

DEVICE = "cuda" if os.environ.get("FORCE_CPU") != "1" else "cpu"
PANELS = Path(os.environ.get("PANELS", "/opt/crossmodal_panels.json"))
OUT = Path(os.environ.get("OUT", "/root/adambind_out/adambind_result.json"))
ADAMBIND_DIR = Path(os.environ.get("ADAMBIND_DIR", "/opt/AdaMBind"))
WORK = Path(os.environ.get("WORK", "/root/adambind_work"))        # scratch for TestbedDataset .pt files
BASE_DATASET = os.environ.get("BASE_DATASET", "BindingDB_Kd")     # PyTDC base set for meta-training
MAX_BASE_TASKS = int(os.environ.get("MAX_BASE_TASKS", "120"))     # cap #proteins (tasks) for runtime
MIN_TASK_SIZE = int(os.environ.get("MIN_TASK_SIZE", "12"))        # need enough pairs/protein for support+query
MAX_TASK_SIZE = int(os.environ.get("MAX_TASK_SIZE", "60"))        # cap pairs/protein
META_ITERS = int(os.environ.get("META_ITERS", "3"))               # outer MAML iters (overnight-cheap)
TASKS_PER_ITER = int(os.environ.get("TASKS_PER_ITER", "40"))      # tasks sampled per outer iter
KSHOT = int(os.environ.get("KSHOT", "5"))                         # few-shot support size
FEWSHOT_REPEATS = int(os.environ.get("FEWSHOT_REPEATS", "8"))     # random support draws to average over
SEED = int(os.environ.get("SEED", "168"))
BIND_HI, BIND_LO = 8.0, 4.0                                       # pseudo-pKd for binder / decoy labels

random.seed(SEED); np.random.seed(SEED)


def auroc(labels, scores):
    from sklearn.metrics import roc_auc_score
    if len(set(labels)) < 2 or len(labels) < 3:
        return None
    return float(roc_auc_score(labels, scores))


def section(fn, name, results):
    try:
        results[name] = fn()
        print(f"[ok] {name}", flush=True)
    except Exception as e:
        results[name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[FAIL] {name}: {e}\n{traceback.format_exc()[:1200]}", flush=True)


# ----------------- import AdaMBind's exact feature extraction + model + trainer -----------------
def _load_create_data_module():
    """create_data.py runs dataset-prep code at import; load it as a module but only grab the helpers.
    It references `seq_dict`/`max_seq_len` as module globals inside seq_cat, so we exec it with a guard
    so the bottom prep block (which reads CSVs that don't exist here) can't abort the helper defs."""
    src = (ADAMBIND_DIR / "create_data.py").read_text()
    # truncate at the dataset-prep block so importing never touches missing CSVs / writes .pt files
    marker = "\nr='/AdaMBind/data/'"
    if marker in src:
        src = src.split(marker)[0]
    mod = types.ModuleType("adambind_create_data")
    mod.__dict__["__file__"] = str(ADAMBIND_DIR / "create_data.py")
    sys.modules["adambind_create_data"] = mod
    exec(compile(src, str(ADAMBIND_DIR / "create_data.py"), "exec"), mod.__dict__)
    return mod


class Args:
    """Mirror train.py's argparse defaults that Trainer.train/predict read off `args`."""
    def __init__(self):
        self.reg_lr = 1e-4
        self.meta_lr = 1e-5
        self.update_step_train = 5
        self.update_step_test = 3
        self.batch_size = 8
        self.noise = 0            # disable label noise at eval time (deterministic scoring)
        self.noise_val = 0.2


class AdaMBind:
    def __init__(self):
        import torch
        sys.path.insert(0, str(ADAMBIND_DIR))                  # so `from utils...`, `from model...` resolve
        self.torch = torch
        self.cd = _load_create_data_module()                   # smile_to_graph, seq_cat, seq_dict, max_seq_len
        from utils.TestbedDataset import TestbedDataset
        from model.gat_gcn import GAT_GCN
        from model.Trainer import Trainer
        self.TestbedDataset = TestbedDataset
        self.GAT_GCN = GAT_GCN
        self.Trainer = Trainer
        self.args = Args()
        self._ds_counter = 0
        WORK.mkdir(parents=True, exist_ok=True)
        self.net = GAT_GCN().to(DEVICE)
        self.trainer = Trainer(self.net)                       # snapshots init weights == zero-shot meta-init

    # --- build PyG Data objects through AdaMBind's own TestbedDataset (exact feature path) ---
    def build_dataset(self, smiles, seqs, ys, tag):
        """smiles: list[str]; seqs: list[str] (raw aa); ys: list[float]. Returns list[PyG Data]."""
        self._ds_counter += 1
        # unique processed file per call so TestbedDataset re-processes (it caches by filename)
        name = f"{tag}_{self._ds_counter}"
        # drop SMILES that RDKit can't parse (smile_to_graph returns None on failure)
        smile_graph, xd, xt, y = {}, [], [], []
        for s, seq, val in zip(smiles, seqs, ys):
            g = self.cd.smile_to_graph(s)
            if g is None:
                print(f"[warn] unparseable SMILES skipped: {s[:40]}", flush=True)
                continue
            smile_graph[s] = g
            xd.append(s)
            xt.append(self.cd.seq_cat(seq))                    # -> np.array length 1000, integer-encoded
            y.append(float(val))
        if not xd:
            raise ValueError(f"no parseable compounds for {tag}")
        ds = self.TestbedDataset(root=str(WORK), dataset=name,
                                 xd=np.asarray(xd), xt=np.asarray(xt),
                                 y=np.asarray(y), smile_graph=smile_graph)
        return list(ds)

    # --- score a list of (smiles,label) against a target seq with the CURRENT init weights (zero-shot) ---
    def score_zeroshot(self, seq, compounds):
        """Returns list of predicted affinities aligned to `compounds`. Uses meta-init net, NO adaptation."""
        from torch_geometric.loader import DataLoader
        data_list = self.build_dataset([c["smiles"] for c in compounds],
                                       [seq] * len(compounds),
                                       [0.0] * len(compounds), tag="score")
        self.net.load_state_dict(self.trainer.get_params())   # restore meta-init (init_params)
        self.net.eval()
        preds = []
        with self.torch.no_grad():
            loader = DataLoader(data_list, batch_size=4, shuffle=False)
            for batch in loader:
                batch = batch.to(DEVICE)
                out = self.net(batch).cpu().numpy().reshape(-1)
                preds.extend([float(v) for v in out])
        return preds

    # --- few-shot: adapt on a support set of labeled panel pairs, predict the held-out query ---
    def score_fewshot(self, seq, support, query):
        """support/query: lists of compound dicts (with 'smiles','label'). Pseudo-affinity from label.
        Returns (query_preds aligned to `query`)."""
        def pseudo(c):
            return BIND_HI if c["label"] == 1 else BIND_LO
        s_list = self.build_dataset([c["smiles"] for c in support], [seq] * len(support),
                                    [pseudo(c) for c in support], tag="support")
        q_list = self.build_dataset([c["smiles"] for c in query], [seq] * len(query),
                                    [pseudo(c) for c in query], tag="query")
        F_data = {seq: [s_list, q_list]}
        # exact AdaMBind adaptation API: inner-loop adapt -> fast_weights; then predict the query set
        fast_weights = self.trainer.train(self.net, self.args, 0, [seq], F_data, update=0)
        preds, labels = self.trainer.predict(self.net, self.args, [seq], F_data, fast_weights, ct=False)
        return list(np.asarray(preds).reshape(-1))


# ----------------- meta-training on a PyTDC base set -----------------
def fetch_base_tasks():
    """PyTDC DTI -> {protein_seq: [(smiles, pkd), ...]} grouped by protein, capped for runtime.
    BindingDB_Kd gives Kd; convert to pKd = -log10(Kd[nM] * 1e-9). Davis/KIBA already log-scaled."""
    from tdc.multi_pred import DTI
    data = DTI(name=BASE_DATASET)
    df = data.get_data()  # columns: Drug_ID, Drug(SMILES), Target_ID, Target(seq), Y
    rng = np.random.RandomState(SEED)
    # affinity transform
    name = BASE_DATASET.lower()
    if "bindingdb" in name:  # Y in nM
        y = df["Y"].astype(float).clip(lower=1e-4)
        df = df.assign(_aff=9.0 - np.log10(y.values))  # pKd = -log10(M) = 9 - log10(nM)
    else:
        df = df.assign(_aff=df["Y"].astype(float))      # davis/kiba already log
    groups = {}
    for seq, g in df.groupby("Target"):
        sub = g.dropna(subset=["Drug", "_aff"])
        if len(sub) < MIN_TASK_SIZE:
            continue
        if len(sub) > MAX_TASK_SIZE:
            sub = sub.sample(MAX_TASK_SIZE, random_state=SEED)
        groups[seq] = list(zip(sub["Drug"].tolist(), sub["_aff"].astype(float).tolist()))
    seqs = list(groups.keys())
    rng.shuffle(seqs)
    seqs = seqs[:MAX_BASE_TASKS]
    return {s: groups[s] for s in seqs}


def meta_train(model: "AdaMBind", base_tasks):
    """Run AdaMBind's MAML outer loop (without the optional adaptive-task scheduler, which is an
    enhancement on top of base MAML, not the core few-shot mechanism). For each sampled task we call
    trainer.train(update=0) (inner adapt -> fast_weights, banks per-task grads) then trainer.train(update=1)
    (applies the averaged meta-gradient + updates init_params), exactly as train.py does per task."""
    args = model.args
    F_data = {}
    print(f"[meta] building PyG datasets for {len(base_tasks)} base tasks...", flush=True)
    for seq, pairs in base_tasks.items():
        smiles = [p[0] for p in pairs]; ys = [p[1] for p in pairs]
        try:
            data_list = model.build_dataset(smiles, [seq] * len(smiles), ys, tag="base")
        except Exception as e:
            print(f"[meta][warn] task build failed ({e}); skipping", flush=True)
            continue
        random.shuffle(data_list)
        nsup = max(KSHOT, len(data_list) // 2)
        F_data[seq] = [data_list[:nsup], data_list[nsup:]]
    F_data = {k: v for k, v in F_data.items() if len(v[1]) > 0}
    task_keys = list(F_data.keys())
    print(f"[meta] {len(task_keys)} usable base tasks", flush=True)
    if len(task_keys) < 2:
        raise ValueError("insufficient base tasks for meta-training")
    rng = np.random.RandomState(SEED)
    for it in range(META_ITERS):
        if (it + 1) % 2 == 0:
            args.meta_lr *= 0.8617
            args.reg_lr *= 0.7617
        picks = rng.choice(task_keys, size=min(TASKS_PER_ITER, len(task_keys)), replace=False)
        for c, tk in enumerate(picks):
            # inner adapt (banks grads), then outer meta-update with update=1 (mirrors train.py)
            _ = model.trainer.train(model.net, args, it, [tk], F_data, update=0)
            model.trainer.train(model.net, args, it, [tk], F_data, count=c, update=1)
        print(f"[meta] iter {it+1}/{META_ITERS} done ({len(picks)} tasks)", flush=True)
    return {"base_dataset": BASE_DATASET, "n_base_tasks": len(task_keys),
            "meta_iters": META_ITERS, "tasks_per_iter": TASKS_PER_ITER}


def main():
    panels = json.loads(PANELS.read_text())
    R = {}
    model = AdaMBind()

    # M. meta-train the base learner (banks meta-init weights == zero-shot model)
    def do_meta():
        base = fetch_base_tasks()
        meta = meta_train(model, base)
        return meta
    section(do_meta, "M_meta_train", R)

    # A. zero-shot binder-vs-decoy AUROC per target
    def zeroshot():
        out = {}
        for key, p in panels.items():
            comps = p["compounds"]
            preds = model.score_zeroshot(p["protein_seq"], comps)
            lab = [c["label"] for c in comps]
            out[key] = {"target": p["target"], "n": len(comps),
                        "auroc": auroc(lab, preds),
                        "scores": {c["drug"]: round(float(s), 4) for c, s in zip(comps, preds)}}
        return out
    section(zeroshot, "A_zeroshot_auroc", R)

    # B. few-shot (k=5): stratified support, predict the rest, average over random draws
    def fewshot():
        out = {}
        for key, p in panels.items():
            comps = p["compounds"]
            pos = [c for c in comps if c["label"] == 1]
            neg = [c for c in comps if c["label"] == 0]
            k_pos = min(len(pos) - 1, max(1, KSHOT // 2))
            k_neg = min(len(neg) - 1, KSHOT - k_pos)
            if k_pos < 1 or k_neg < 1 or (len(pos) - k_pos) < 1 or (len(neg) - k_neg) < 1:
                out[key] = {"target": p["target"], "skip": "too few compounds for stratified k-shot"}
                continue
            aurocs, per_repeat = [], []
            rng = np.random.RandomState(SEED)
            for rep in range(FEWSHOT_REPEATS):
                sp = list(rng.choice(len(pos), k_pos, replace=False))
                sn = list(rng.choice(len(neg), k_neg, replace=False))
                support = [pos[i] for i in sp] + [neg[i] for i in sn]
                query = [pos[i] for i in range(len(pos)) if i not in sp] + \
                        [neg[i] for i in range(len(neg)) if i not in sn]
                try:
                    qpreds = model.score_fewshot(p["protein_seq"], support, query)
                    qlab = [c["label"] for c in query]
                    a = auroc(qlab, qpreds)
                    if a is not None:
                        aurocs.append(a)
                    per_repeat.append({"rep": rep, "k_support": len(support),
                                       "n_query": len(query), "auroc": a})
                except Exception as e:
                    per_repeat.append({"rep": rep, "error": f"{type(e).__name__}: {e}"})
            out[key] = {"target": p["target"], "k_shot": KSHOT, "repeats": FEWSHOT_REPEATS,
                        "mean_auroc": round(float(np.mean(aurocs)), 4) if aurocs else None,
                        "sd_auroc": round(float(np.std(aurocs)), 4) if aurocs else None,
                        "n_valid": len(aurocs), "per_repeat": per_repeat}
        return out
    section(fewshot, "B_fewshot_k5_auroc", R)

    # C. per-compound zero-shot scores for the head-to-head table (alongside boltz_prob_binder already in panel)
    def headtohead():
        out = {}
        for key, p in panels.items():
            comps = p["compounds"]
            preds = model.score_zeroshot(p["protein_seq"], comps)
            out[key] = {"target": p["target"],
                        "rows": [{"drug": c["drug"], "label": c["label"],
                                  "adambind_zeroshot": round(float(s), 4),
                                  "boltz_prob_binder": c.get("boltz_prob_binder")}
                                 for c, s in zip(comps, preds)]}
        return out
    section(headtohead, "C_head_to_head", R)

    payload = {
        "model": "AdaMBind (GAT_GCN drug graph + 1D-CNN protein, MAML meta-learning, regressed affinity)",
        "repo": "https://github.com/Moohyun-w/AdaMBind",
        "license": "NO LICENSE FILE (all-rights-reserved) — eval/research only",
        "weights": "none shipped; meta-trained on-instance from PyTDC " + BASE_DATASET,
        "phase": "Track 2/3 DTI few-shot characterization",
        "config": {"kshot": KSHOT, "fewshot_repeats": FEWSHOT_REPEATS, "meta_iters": META_ITERS,
                   "base_dataset": BASE_DATASET, "seed": SEED,
                   "pseudo_affinity": {"binder": BIND_HI, "decoy": BIND_LO}},
        "baselines": {"balm_nav18_n11": 0.857, "balm_mtor_n7": 1.000,
                      "boltz2_nav18": 0.714, "boltz2_mtor": 1.000, "conplex_nav": 0.437},
        "results": R,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"[done] wrote {OUT}", flush=True)
    summary = {}
    if isinstance(R.get("A_zeroshot_auroc"), dict):
        summary["zeroshot"] = {k: v.get("auroc") for k, v in R["A_zeroshot_auroc"].items()
                               if isinstance(v, dict)}
    if isinstance(R.get("B_fewshot_k5_auroc"), dict):
        summary["fewshot"] = {k: v.get("mean_auroc") for k, v in R["B_fewshot_k5_auroc"].items()
                              if isinstance(v, dict)}
    print(json.dumps(summary, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
