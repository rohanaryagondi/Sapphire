"""baselines.conplex — thin wrapper around ConPLex (Singh et al., PNAS 2023).

ConPLex (github.com/samsledje/ConPLex) is a contrastive protein-language-model DTI
model: it co-embeds a target sequence and a drug SMILES and returns a binding
PROBABILITY in [0, 1]. That is exactly the single-target binder-vs-decoy axis
MAMMAL's off-the-shelf DTI head fails at — the reason it's the headline challenger.

WHY A SUBPROCESS: ConPLex's deps conflict with the `mammal` conda env, so it lives
in its OWN env (`conplex`). Its CLI (`conplex-dti predict`) also eagerly imports a
training stack (tdc/wandb/pytorch_lightning) we deliberately did not install, so we
bypass the CLI and call a standalone driver (`baselines/_conplex_predict.py`) that
imports only the clean predict-path modules. This wrapper — imported from the
`mammal` env by the compare scripts — shells out to the conplex env's python running
that driver against a temp TSV, and parses the prediction column. Batch everything
into ONE call: the model is reloaded per invocation.

Score semantics: ConPLex emits a probability, NOT a calibrated pKd. Per
baselines.common's governing rule it is only ever compared by rank (AUROC /
Spearman / enrichment), never by absolute value.
"""

from __future__ import annotations

import csv
import os
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# The conplex env's python + our standalone driver (NOT the conplex-dti CLI).
CONPLEX_PY = os.environ.get("CONPLEX_PY", "/opt/anaconda3/envs/conplex/bin/python")
DRIVER = str(Path(__file__).resolve().parent / "_conplex_predict.py")
# Where the pretrained checkpoint is cached (gitignored, like models/).
CONPLEX_DIR = Path(os.environ.get("CONPLEX_DIR", REPO / "models" / "conplex"))
MODEL_NAME = "ConPLex_v1_BindingDB"
# NB: the README's /cb/... URL 301-redirects to an http:// path that times out;
# this is the working HTTPS location (no /cb prefix).
MODEL_URL = "https://cb.csail.mit.edu/conplex/data/models/BindingDB_ExperimentalValidModel.pt"


def model_path() -> Path:
    return CONPLEX_DIR / f"{MODEL_NAME}.pt"


def ensure_model() -> Path:
    """Download the pretrained ConPLex BindingDB checkpoint (curl) if not present."""
    mp = model_path()
    if mp.is_file():
        return mp
    CONPLEX_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(["curl", "-fL", "--retry", "3", "-o", str(mp), MODEL_URL], check=True)
    if not mp.is_file():
        raise FileNotFoundError(f"ConPLex checkpoint not downloaded to {mp}")
    return mp


def score_batch(pairs, model_pt: str | Path | None = None) -> list[float]:
    """Score an ordered list of (protein_seq, smiles) pairs → list of probabilities in [0,1].

    One CLI call for the whole batch. Alignment is preserved by tagging each row
    with its integer index as the protein/molecule ID and re-mapping the output
    (the CLI may dedupe/reorder rows)."""
    pairs = list(pairs)
    if not pairs:
        return []
    mp = Path(model_pt) if model_pt else ensure_model()

    with tempfile.TemporaryDirectory() as td:
        in_tsv = Path(td) / "pairs.tsv"
        out_tsv = Path(td) / "preds.tsv"
        # ConPLex predict input: protein_ID  molecule_ID  protein_sequence  SMILES  (no header)
        with in_tsv.open("w", newline="") as fh:
            w = csv.writer(fh, delimiter="\t")
            for i, (seq, smi) in enumerate(pairs):
                w.writerow([f"P{i}", f"M{i}", seq, smi])
        proc = subprocess.run(
            [CONPLEX_PY, DRIVER,
             "--data-file", str(in_tsv),
             "--model-path", str(mp),
             "--outfile", str(out_tsv),
             "--data-cache-dir", td,
             "--device", "cpu"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not out_tsv.is_file():
            raise RuntimeError(
                f"ConPLex predict driver failed (rc={proc.returncode}).\n"
                f"STDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-2000:]}"
            )
        # Parse: map row index -> score. The predicted score is the last numeric column;
        # the molecule_ID column (M<i>) carries our index so we re-align robustly.
        scores: dict[int, float] = {}
        with out_tsv.open() as fh:
            for row in csv.reader(fh, delimiter="\t"):
                if not row:
                    continue
                idx = _row_index(row)
                val = _last_float(row)
                if idx is not None and val is not None:
                    scores[idx] = val
    missing = [i for i in range(len(pairs)) if i not in scores]
    if missing:
        raise RuntimeError(f"ConPLex returned no score for {len(missing)} rows (e.g. idx {missing[:5]})")
    return [scores[i] for i in range(len(pairs))]


def _row_index(row) -> int | None:
    for cell in row:
        c = cell.strip()
        if c.startswith("M") and c[1:].isdigit():
            return int(c[1:])
    return None


def _last_float(row) -> float | None:
    for cell in reversed(row):
        try:
            return float(cell)
        except (ValueError, TypeError):
            continue
    return None


class ConplexScorer:
    """Scorer-protocol adapter (baselines.common.Scorer)."""

    name = "ConPLex"
    kind = "probability"
    runs_full_screen = True

    def __init__(self, model_pt: str | Path | None = None):
        self._mp = Path(model_pt) if model_pt else ensure_model()

    def score_pair(self, protein_seq: str, smiles: str) -> float:
        return score_batch([(protein_seq, smiles)], self._mp)[0]

    def score_batch(self, pairs):
        return score_batch(pairs, self._mp)


if __name__ == "__main__":
    # Smoke test: a known strong binder should outscore an obvious non-binder on
    # the same target. Imatinib binds ABL1 (P00519); metformin does not.
    import sys
    sys.path.insert(0, str(REPO))
    from mammal_quiver.sequences import fetch_uniprot_sequence

    abl1 = fetch_uniprot_sequence("P00519")
    imatinib = "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1"
    metformin = "CN(C)C(=N)N=C(N)N"
    s_bind, s_decoy = score_batch([(abl1, imatinib), (abl1, metformin)])
    print(f"ConPLex imatinib/ABL1 = {s_bind:.4f}   metformin/ABL1 = {s_decoy:.4f}")
    print("PASS — binder > decoy" if s_bind > s_decoy else "WARN — binder did NOT outscore decoy")
