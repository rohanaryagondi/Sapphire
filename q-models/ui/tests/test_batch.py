"""Tests for batch triage, the read-only doc route, and DTI truncation reporting.

Fast tests (default) never load a model — they exercise the batch envelope
(validation, per-row error capture, the row cap), the `/doc` path security, and
the pure truncation helper. The one ranked-batch test that needs real scores is
marked `slow`.

    pytest ui/tests/test_batch.py -m "not slow"     # fast
    pytest ui/tests/test_batch.py                    # + a real ranked batch
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ui.backend.app import MAX_BATCH_ROWS, app  # noqa: E402
from ui.backend.mammal_runner import dti_truncation_info  # noqa: E402

client = TestClient(app)

_CAFFEINE = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
_IBUPROFEN = "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"


# --------------------------------- batch: fast (no model) ---------------------------------

def test_batch_empty_rows_422():
    assert client.post("/predict/bbbp/batch", json={"rows": []}).status_code == 422


def test_batch_missing_rows_422():
    assert client.post("/predict/bbbp/batch", json={}).status_code == 422


def test_batch_unsupported_task_404():
    # generation/embeddings have no single-prediction row model → not batchable.
    assert client.post("/predict/generation/batch", json={"rows": [{"prompt": "x"}]}).status_code == 404
    assert client.post("/predict/nope/batch", json={"rows": [{"smiles": "CCO"}]}).status_code == 404


def test_batch_all_bad_smiles_are_error_rows_no_model_load():
    """All-invalid SMILES → 200 with per-row errors, reliability attached, model never loads."""
    rows = [{"smiles": "nonsense((("}, {"smiles": "alsobad)))"}]
    r = client.post("/predict/bbbp/batch", json={"rows": rows})
    assert r.status_code == 200
    d = r.json()
    assert d["task"] == "bbbp"
    assert d["requested"] == 2 and d["processed"] == 2 and d["dropped"] == 0
    assert d["reliability"]["badge"] == "caution"        # the verdict travels with the batch
    assert len(d["rows"]) == 2
    for row in d["rows"]:
        assert row["error"]                               # parse failure recorded
        assert row["prediction"] is None
        assert row["rank"] is None                        # errored rows are not ranked


def test_batch_row_cap_reports_dropped_no_model_load():
    """Over the cap → process the cap, report the dropped count (never silently truncate)."""
    n = MAX_BATCH_ROWS + 20
    rows = [{"smiles": "bad((("} for _ in range(n)]      # all invalid → no model load
    r = client.post("/predict/bbbp/batch", json={"rows": rows})
    assert r.status_code == 200
    d = r.json()
    assert d["requested"] == n
    assert d["processed"] == MAX_BATCH_ROWS
    assert d["dropped"] == 20
    assert len(d["rows"]) == MAX_BATCH_ROWS


def test_batch_does_not_pollute_history_when_all_rows_fail():
    client.delete("/history")
    client.post("/predict/bbbp/batch", json={"rows": [{"smiles": "bad((("}]})
    assert client.get("/history").json()["count"] == 0


# --------------------------------- /doc route: fast ---------------------------------

def test_doc_serves_results_readme():
    r = client.get("/doc/results/README.md")
    assert r.status_code == 200
    assert "text/" in r.headers["content-type"]
    assert len(r.text) > 0


def test_doc_serves_docs_findings():
    assert client.get("/doc/docs/FINDINGS.md").status_code == 200


def test_doc_rejects_path_traversal():
    # Escaping the allowed dirs must never serve a file.
    for bad in ["../CLAUDE.md", "results/../../CLAUDE.md", "/etc/passwd", "../../etc/passwd"]:
        r = client.get(f"/doc/{bad}")
        assert r.status_code in (403, 404), (bad, r.status_code)


def test_doc_rejects_dir_outside_allowlist():
    # Files at repo root or other dirs are not under results/ or docs/ → blocked.
    assert client.get("/doc/CLAUDE.md").status_code in (403, 404)
    assert client.get("/doc/HANDOFF.md").status_code in (403, 404)


def test_doc_missing_file_404():
    assert client.get("/doc/results/does_not_exist_xyz.md").status_code == 404


# --------------------------------- truncation helper: fast ---------------------------------

def test_dti_truncation_info_short_sequence():
    info = dti_truncation_info("M" * 300)
    assert info["target_len"] == 300
    assert info["target_truncated"] is False


def test_dti_truncation_info_long_sequence_flagged():
    info = dti_truncation_info("M" * 1400)        # Nav1.8 is ~1956 aa — binding region is lost
    assert info["target_len"] == 1400
    assert info["target_truncated"] is True


# --------------------------------- batch: slow (real scores, ranking) ---------------------------------

@pytest.mark.slow
def test_batch_bbbp_ranks_valid_compounds():
    rows = [{"smiles": _CAFFEINE}, {"smiles": _IBUPROFEN}, {"smiles": "bad((("}]
    r = client.post("/predict/bbbp/batch", json={"rows": rows})
    assert r.status_code == 200
    d = r.json()
    assert d["processed"] == 3
    ranked = [row for row in d["rows"] if row["rank"] is not None]
    assert len(ranked) == 2                                   # two valid, one error
    # ranks are dense 1..k and ordered by descending score
    assert [row["rank"] for row in ranked] == [1, 2]
    assert ranked[0]["prediction"]["value"] >= ranked[1]["prediction"]["value"]
    assert all(row["prediction"]["score_kind"] == "normalized_p1" for row in ranked)
    # the standardized SMILES that was actually scored is reported per row
    assert ranked[0]["standardized_smiles"]
