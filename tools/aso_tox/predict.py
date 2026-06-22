"""
predict.py — ASO acute-toxicity prediction CLI (Quiver / Sapphire delegate).

Scientific logic copied VERBATIM from ASO_tox_prediction_pipeline.ipynb.
Do NOT alter coefficients, ranges, rounding, or feature math.

Usage:
    python predict.py sequences.csv
    echo '["GCAC...","TTGC..."]' | python predict.py --json
    echo '{"sequences":["GCAC..."]}' | python predict.py --json
"""
from __future__ import annotations

import json
import os
import sys
import warnings

# Suppress sklearn version warnings to stderr only — stdout must be clean JSON.
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import numpy as np
import joblib

# ---------------------------------------------------------------------------
# VERBATIM from ASO_tox_prediction_pipeline.ipynb  — do NOT edit
# ---------------------------------------------------------------------------
FEATURE_COLS = [
    'MaxLength_A', 'MaxLength_T', 'MaxLength_G', 'MaxLength_C',
    'Number_A', 'Number_C', 'Number_T', 'Number_G',
    'Length_Gfree_5', 'Length_Gfree_3'
]

TOX_THRESHOLD = 1.0  # Ionis scale: >1.0 = Toxic


def extract_features(seq):
    seq = seq.upper().strip(); n = len(seq); f = {}
    for base in ['A', 'T', 'G', 'C']:
        max_run = 0
        for r in range(1, 7):
            if base * r in seq: max_run = r
        f[f'MaxLength_{base}'] = max_run
    for b in ['A', 'T', 'G', 'C']: f[f'Number_{b}'] = seq.count(b)
    Gfree5 = n
    for k in range(n):
        if seq[k] == 'G': Gfree5 = k; break
    f['Length_Gfree_5'] = Gfree5
    Gfree3 = n
    for k in range(n - 1, -1, -1):
        if seq[k] == 'G': Gfree3 = n - 1 - k; break
    f['Length_Gfree_3'] = Gfree3
    return f


def hagedorn_score(f):
    return (136.0430
            - 3.1263 * f['Number_A']
            - 5.1100 * f['Number_C']
            - 4.7217 * f['Number_T']
            - 10.1264 * f['Number_G']
            + 1.3577 * f['Length_Gfree_3'])

# ---------------------------------------------------------------------------
# END verbatim section
# ---------------------------------------------------------------------------


def _load_model():
    # TRUSTED source: aso_tox_gbr_model.pkl is a first-party artifact produced by Quiver
    # and committed directly into this repo at tools/aso_tox/. It is not accepted from
    # user-supplied paths or network locations, so joblib.load is safe here.
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "aso_tox_gbr_model.pkl")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return joblib.load(model_path)


def _predict_sequences(sequences: list[str], model) -> list[dict]:
    results = []
    for seq in sequences:
        f = extract_features(seq)
        hag = hagedorn_score(f)
        features_ordered = [f[col] for col in FEATURE_COLS]
        gbr = float(model.predict([features_ordered])[0])
        label = 'Toxic' if gbr > TOX_THRESHOLD else 'Non-toxic'
        results.append({
            "sequence": seq,
            "hagedorn_predict_toxscore": float(np.round(hag, 4)),
            "gbr_predict_toxscore": float(np.round(gbr, 9)),
            "tox_label": label,
            "features": {k: f[k] for k in FEATURE_COLS},
        })
    return results


def _read_csv_sequences(csv_path: str) -> list[str]:
    import csv
    seqs = []
    col_names = {'Sequence', 'sequence', 'ASO'}
    with open(csv_path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        col = None
        for name in (reader.fieldnames or []):
            if name in col_names:
                col = name
                break
        if col is None:
            raise ValueError(f"No sequence column found (looked for: {col_names}). "
                             f"Got: {reader.fieldnames}")
        for row in reader:
            val = row[col].strip()
            if val:
                seqs.append(val)
    return seqs


def main():
    use_json = '--json' in sys.argv
    csv_path = None
    for arg in sys.argv[1:]:
        if arg != '--json':
            csv_path = arg
            break

    model = _load_model()
    p = model.get_params()

    if use_json:
        raw = sys.stdin.read().strip()
        data = json.loads(raw)
        if isinstance(data, list):
            sequences = data
        elif isinstance(data, dict):
            sequences = data.get("sequences", [])
        else:
            sequences = []
    elif csv_path:
        sequences = _read_csv_sequences(csv_path)
    else:
        print(json.dumps({"error": "No input: provide a CSV path or --json", "provenance": "aso-tox"}))
        sys.exit(1)

    predictions = _predict_sequences(sequences, model)

    output = {
        "provenance": "aso-tox",
        "threshold": TOX_THRESHOLD,
        "model_params": {
            "n_estimators": p.get("n_estimators"),
            "max_depth": p.get("max_depth"),
            "learning_rate": p.get("learning_rate"),
        },
        "predictions": predictions,
    }

    print(json.dumps(output))


if __name__ == "__main__":
    main()
