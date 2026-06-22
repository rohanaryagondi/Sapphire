# ASO Acute-Toxicity Tool (`aso-tox`)

Sequence-based acute toxicity screening for antisense oligonucleotides (ASOs).
Combines the Hagedorn linear base model with a Zhang-lab GradientBoostingRegressor (GBR).
Threshold: GBR score > 1.0 = **Toxic** (Ionis scale).

Trained on Ionis UBE3A + GFAP ASO datasets (n = 894 ASOs, combined).

---

## How to call

**From a CSV file** (must have a column named `Sequence`, `sequence`, or `ASO`):
```bash
python tools/aso_tox/predict.py path/to/seqs.csv
```

**From JSON stdin:**
```bash
echo '["GCACTTGAATTTCACGTTGT","GGTGAATCTTTATTAAAC"]' | python tools/aso_tox/predict.py --json
# or with explicit key:
echo '{"sequences":["GCACTTGAATTTCACGTTGT"]}' | python tools/aso_tox/predict.py --json
```

---

## JSON output schema

```json
{
  "provenance": "aso-tox",
  "threshold": 1.0,
  "model_params": {
    "n_estimators": <int>,
    "max_depth": <int>,
    "learning_rate": <float>
  },
  "predictions": [
    {
      "sequence": "GCACTTGAATTTCACGTTGT",
      "hagedorn_predict_toxscore": 26.1763,
      "gbr_predict_toxscore": 1.884452123,
      "tox_label": "Toxic",
      "features": {
        "MaxLength_A": 2, "MaxLength_T": 2, "MaxLength_G": 1, "MaxLength_C": 1,
        "Number_A": 2, "Number_C": 3, "Number_T": 7, "Number_G": 3,
        "Length_Gfree_5": 3, "Length_Gfree_3": 5
      }
    }
  ]
}
```

Rounding: Hagedorn `np.round(..., 4)`, GBR `np.round(..., 9)`.

---

## How it fits Sapphire

- **Agent ID:** `aso-tox`
- **Kind:** `python` (external subprocess delegate — the orchestrator runtime is stdlib-only; it shells out to this script via `sapphire-orchestrator/tools/aso_tox_seam.py`)
- **Bucket:** Bucket-1 safety fact source
- **Provenance label:** `aso-tox`

The seam (`aso_tox_seam.py`) exposes two callables:
- `predict(sequences)` — raw JSON output
- `predict_findings(inputs)` — harness-compatible `findings` dict (one `T2` fact per sequence)

### ASO-Design pairing

This tool is designed to chain with the (forthcoming) ASO-Design tool:
```
Design tool → candidate ASO sequences → aso-tox screen → findings in dossier
```
When no sequences are present in the inputs (a normal target-level query), `predict_findings` returns `facts: []` — an honest empty, not an error.

---

## What's missing

- **Sequence-input path in `run_live` (active task).** The orchestrator dispatches `aso-tox` in Bucket-1, but `run_live` has no channel to pass ASO sequences to it — so in a live run it always receives zero sequences and returns `facts: []`. The tool is correct; the *feed* is missing. Tracked at `docs/superpowers/plans/2026-06-22-aso-tox-sequence-wiring.md`. This is the same channel the forthcoming ASO-Design tool will populate.
- **Training CSVs** `UBE3A_ATS_ASO_info_v2.csv` and `GFAP_ASO_withICV_score_v2.csv` are not included in this repo — they are needed only to retrain or validate from scratch. Contact the model author (Hongkang) for access.
- **scikit-learn version pin:** The pkl was serialized with scikit-learn 1.8.0. Loading on 1.6.1 works but emits an `InconsistentVersionWarning`. Pin `scikit-learn==1.8.0` in `requirements.txt` for production fidelity; confirm the exact version with the model author.
