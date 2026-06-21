"""baselines.boltz — Boltz-2 affinity wrapper + a budget guard + a results lookup.

Boltz-2 (github.com/jwohlwend/boltz) is an AlphaFold3-class co-folding model with a
binding-AFFINITY head that approaches FEP accuracy. It is the "most important
competitor to flag" for DTI: it does structure (MAMMAL has none) AND affinity
(MAMMAL does poorly), and is equally open (MIT).

COST REALITY — this is the gated, expensive model:
  * Affinity needs ~20-30 GB VRAM, so it runs on AWS g5.xlarge (A10G 24 GB), NOT a
    T4. The whole evaluation is hard-capped at $2, so Boltz scores only a tightly
    bounded subset of pairs (BOLTZ_PAIR_BUDGET) — it is a per-pair oracle, not a
    screening tool. `runs_full_screen = False`.
  * Big targets OOM: Nav1.8 (SCN10A, ~1956 aa) must be run as a binding-DOMAIN
    construct (≤ ~400-500 aa). The construct used per pair is recorded.

WORKFLOW SPLIT:
  * write_affinity_yaml / run_boltz_affinity / read_affinity / score_pair run ON AWS
    (where `boltz` is installed + a GPU exists). A local CPU proof-of-concept on a
    tiny construct validates the YAML + parser before any AWS spend.
  * boltz_lookup / boltz_scores run in the `mammal` env inside the compare scripts:
    they read the consolidated results JSON the AWS run produced and return the
    prob-binder for pairs Boltz actually scored (None otherwise → "N/A over budget").

Readout: `affinity_probability_binary` (primary, binder-vs-decoy, comparable by rank)
and `affinity_pred_value` = predicted log10(IC50 µM) (secondary potency).
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Per-pair compute is minutes on an A10G; this cap keeps the AWS session under $2.
BOLTZ_PAIR_BUDGET = int(os.environ.get("BOLTZ_PAIR_BUDGET", "35"))


# --------------------------------------------------------------------------- #
# AWS-side: build inputs, run, parse  (require `boltz` + a GPU)                 #
# --------------------------------------------------------------------------- #
def write_affinity_yaml(protein_seq: str, smiles: str, out_path: str | Path) -> Path:
    """Emit a Boltz-2 affinity YAML (protein chain A + ligand B, affinity on B)."""
    out_path = Path(out_path)
    out_path.write_text(
        "version: 1\n"
        "sequences:\n"
        "  - protein:\n"
        "      id: A\n"
        f"      sequence: {protein_seq}\n"
        "  - ligand:\n"
        "      id: B\n"
        f"      smiles: '{smiles}'\n"
        "properties:\n"
        "  - affinity:\n"
        "      binder: B\n"
    )
    return out_path


def run_boltz_affinity(yaml_path: str | Path, out_dir: str | Path, cache: str | Path | None = None,
                       accelerator: str = "gpu", sampling_steps_affinity: int = 100,
                       diffusion_samples_affinity: int = 3, use_msa_server: bool = True) -> Path:
    """Shell out to `boltz predict` for one affinity YAML. Returns the out_dir."""
    out_dir = Path(out_dir)
    cmd = ["boltz", "predict", str(yaml_path), "--out_dir", str(out_dir),
           "--accelerator", accelerator,
           "--sampling_steps_affinity", str(sampling_steps_affinity),
           "--diffusion_samples_affinity", str(diffusion_samples_affinity)]
    if use_msa_server:
        cmd.append("--use_msa_server")
    if cache:
        cmd += ["--cache", str(cache)]
    subprocess.run(cmd, check=True)
    return out_dir


def read_affinity(out_dir: str | Path) -> dict:
    """Parse Boltz-2's affinity_*.json under out_dir → {prob_binder, log_ic50}."""
    hits = glob.glob(str(Path(out_dir) / "**" / "affinity_*.json"), recursive=True)
    if not hits:
        raise FileNotFoundError(f"no affinity_*.json under {out_dir}")
    data = json.loads(Path(hits[0]).read_text())
    return {
        "prob_binder": float(data.get("affinity_probability_binary")),
        "log_ic50": float(data["affinity_pred_value"]) if "affinity_pred_value" in data else None,
    }


def estimate_cost(n_pairs: int, sec_per_pair: float = 240.0, usd_per_hr: float = 1.006) -> dict:
    """Rough $ estimate for an A10G g5.xlarge run; refuses if over BOLTZ_PAIR_BUDGET."""
    if n_pairs > BOLTZ_PAIR_BUDGET:
        raise ValueError(
            f"{n_pairs} pairs exceeds BOLTZ_PAIR_BUDGET={BOLTZ_PAIR_BUDGET} — Boltz is a per-pair "
            f"oracle under a $2 cap; shrink the subset or raise the budget deliberately."
        )
    hours = n_pairs * sec_per_pair / 3600.0
    return {"n_pairs": n_pairs, "est_hours": round(hours, 2), "est_usd": round(hours * usd_per_hr, 2)}


# --------------------------------------------------------------------------- #
# mammal-env side: read precomputed AWS results into the compare scripts        #
# --------------------------------------------------------------------------- #
def _latest_results() -> Path | None:
    hits = sorted(glob.glob(str(REPO / "results" / "boltz_affinity_*.json")))
    return Path(hits[-1]) if hits else None


def boltz_lookup(path: str | Path | None = None) -> dict:
    """Load the consolidated Boltz results → {(protein_seq, smiles): {prob_binder, log_ic50}}.

    Returns {} if no Boltz run exists yet (so compare scripts degrade to MAMMAL+ConPLex
    and mark Boltz cells "N/A — pending AWS")."""
    path = Path(path) if path else _latest_results()
    if not path or not Path(path).is_file():
        return {}
    data = json.loads(Path(path).read_text())
    out = {}
    for rec in data.get("pairs", []):
        out[(rec["protein_seq"], rec["smiles"])] = {
            "prob_binder": rec.get("prob_binder"),
            "log_ic50": rec.get("log_ic50"),
        }
    return out


def boltz_scores(pairs, lookup: dict | None = None) -> list[float | None]:
    """Prob-binder for each (seq, smiles); None where Boltz did not score the pair."""
    lk = lookup if lookup is not None else boltz_lookup()
    return [(lk.get((s, m)) or {}).get("prob_binder") for s, m in pairs]


class BoltzScorer:
    """Scorer-protocol adapter — AWS-side only (needs `boltz` + GPU)."""

    name = "Boltz-2"
    kind = "affinity"
    runs_full_screen = False

    def __init__(self, cache: str | Path | None = None, accelerator: str = "gpu"):
        self._cache = cache
        self._accel = accelerator

    def score_pair(self, protein_seq: str, smiles: str) -> float:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            y = write_affinity_yaml(protein_seq, smiles, Path(td) / "in.yaml")
            out = run_boltz_affinity(y, Path(td) / "out", cache=self._cache, accelerator=self._accel)
            return read_affinity(out)["prob_binder"]

    def score_batch(self, pairs):
        return [self.score_pair(s, m) for s, m in pairs]
