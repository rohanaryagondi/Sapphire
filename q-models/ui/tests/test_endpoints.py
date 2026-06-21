"""Smoke tests for the Quiver MAMMAL Explorer backend.

Fast tests (default) never load a model — they cover routing, the reliability
overlay wording, schema validation, and frontend serving. Model-loading tests are
marked `slow`:

    pytest -m "not slow"        # fast: routing + reliability + schemas (seconds)
    pytest                      # everything, incl. real predictions (loads checkpoints)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from ui.backend.app import app  # noqa: E402

client = TestClient(app)

PREDICT_TASKS = ["dti", "ppi", "bbbp", "clintox_tox", "clintox_fda", "solubility", "tcr"]
ALL_VERDICT_TASKS = PREDICT_TASKS + ["generation", "embeddings"]
VALID_BADGES = {"reliable", "caution", "dont_use", "low_value", "split"}

_CALMODULIN = ("MADQLTEEQIAEFKEAFSLFDKDGDGTITTKELGTVMRSLGQNPTEAELQDMISELDQDGFIDKEDLHDG"
               "DGKISFEEFLNLVNKEMTADVDGDGQVNYEEFVTMMTSK")
_CALCINEURIN = ("MSSKLLLAGLDIERVLAEKNFYKEWDTWIIEAMNVGDEEVDRIKEFKEDEIFEEAKTLGTAEMQEYKKQKL"
                "EEAIEGAFDIFDKDGNGYISAAELRHVMTNLGEKLTDEEVDEMIRQMWDQNGDWDRIKELKFGEIKKLSAK"
                "DTRGTIFIKVFENLGTGVDSEYEDVSKYMLKHQ")
_CAFFEINE = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"


# --------------------------------- fast ---------------------------------

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    for t in PREDICT_TASKS:
        assert t in d["tasks"], t


def test_reliability_every_task_present_and_shaped():
    for t in ALL_VERDICT_TASKS:
        r = client.get(f"/reliability/{t}")
        assert r.status_code == 200, t
        d = r.json()
        assert d["task"] == t
        assert d["badge"] in VALID_BADGES, (t, d["badge"])
        assert d["headline"] and d["why"] and d["recommended_use"] and d["source"]
        assert d["badge_emoji"] and d["badge_label"]


def test_reliability_verbatim_spot_checks():
    """Guard the §2 wording against accidental softening — it's the product."""
    tox = client.get("/reliability/clintox_tox").json()
    assert tox["badge"] == "dont_use"
    assert "0% sensitivity" in tox["headline"]

    dti = client.get("/reliability/dti").json()
    assert dti["badge"] == "caution"
    assert "phase2b_quiver_targets.md" in dti["source"]

    emb = client.get("/reliability/embeddings").json()
    assert emb["badge"] == "split"
    assert "cross-modal" in emb["why"].lower()

    assert client.get("/reliability/solubility").json()["badge"] == "reliable"
    assert client.get("/reliability/clintox_fda").json()["badge"] == "low_value"


def test_reliability_unknown_404():
    assert client.get("/reliability/not_a_task").status_code == 404


def test_strategic_banner():
    d = client.get("/reliability").json()
    assert "commodity enrichment" in d["banner"]
    assert set(ALL_VERDICT_TASKS).issubset(d["verdicts"].keys())


def test_index_served_same_origin():
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Quiver MAMMAL Explorer" in r.text


def test_examples():
    assert client.get("/examples/dti").json()["uniprot_acc"] == "Q9Y5Y9"
    assert client.get("/examples/ppi").json()["seq_a"].startswith("MADQ")
    assert client.get("/examples/no_such").status_code == 404


def test_schema_validation_422():
    assert client.post("/predict/dti", json={"smiles": "CCO"}).status_code == 422       # no target
    assert client.post("/predict/ppi", json={"seq_a": "AAAA"}).status_code == 422        # missing seq_b
    assert client.post("/predict/bbbp", json={}).status_code == 422                      # missing smiles


def test_bad_smiles_400_without_loading_model():
    # neutral_parent() rejects before any model loads → 400, still a fast test.
    r = client.post("/predict/bbbp", json={"smiles": "this is not a molecule )))"})
    assert r.status_code == 400


def test_history_endpoints_without_loading_model():
    assert client.delete("/history").json()["status"] == "cleared"
    d = client.get("/history").json()
    assert d["count"] == 0 and d["records"] == []
    # a rejected prediction must NOT create a history entry
    client.post("/predict/bbbp", json={"smiles": "nonsense ((("})
    assert client.get("/history").json()["count"] == 0


# --------------------------------- slow (load models) ---------------------------------

@pytest.mark.slow
def test_predict_solubility_slow():
    r = client.post("/predict/solubility", json={"protein_seq": _CALMODULIN})
    assert r.status_code == 200
    d = r.json()
    p = d["prediction"]
    assert p["score_kind"] == "normalized_p1"
    assert 0.0 <= p["value"] <= 1.0
    assert p["pred_class"] in (0, 1)
    assert d["reliability"]["badge"] == "reliable"
    assert len(d["providers"]) == 1
    assert d["providers"][0]["provider_kind"] == "ibm_public"


@pytest.mark.slow
def test_predict_bbbp_slow_normalized_and_standardized():
    r = client.post("/predict/bbbp", json={"smiles": _CAFFEINE})
    assert r.status_code == 200
    d = r.json()
    assert d["prediction"]["score_kind"] == "normalized_p1"
    assert 0.0 <= d["prediction"]["value"] <= 1.0
    assert d["standardized_smiles"]  # standardization ran
    assert d["reliability"]["badge"] == "caution"


@pytest.mark.slow
def test_predict_dti_slow_pkd_via_uniprot():
    suzetrigine = "C[C@H]1[C@H]([C@@H](O[C@@]1(C)C(F)(F)F)C(=O)NC2=CC(=NC=C2)C(=O)N)C3=C(C(=C(C=C3)F)F)OC"
    r = client.post("/predict/dti", json={"smiles": suzetrigine, "uniprot_acc": "Q9Y5Y9"})
    assert r.status_code == 200
    p = r.json()["prediction"]
    assert p["score_kind"] == "pkd"
    assert isinstance(p["value"], float)


@pytest.mark.slow
def test_predict_ppi_slow_sanity_pair():
    # calmodulin–calcineurin is the base model card's PPI sanity pair (documented P≈0.95).
    r = client.post("/predict/ppi", json={"seq_a": _CALMODULIN, "seq_b": _CALCINEURIN})
    assert r.status_code == 200
    p = r.json()["prediction"]
    assert p["score_kind"] == "normalized_p1"
    assert p["value"] > 0.5


@pytest.mark.slow
def test_history_records_a_prediction():
    client.delete("/history")
    client.post("/predict/solubility", json={"protein_seq": _CALMODULIN})
    h = client.get("/history").json()
    assert h["count"] >= 1
    rec = h["records"][0]
    assert rec["task"] == "solubility"
    assert rec["summary"]["score_kind"] == "normalized_p1"
    assert rec["inputs"]["protein_seq"] == _CALMODULIN  # original input retained for re-run


@pytest.mark.slow
def test_generation_and_embeddings_slow():
    g = client.post("/predict/generation", json={"prompt": _CAFFEINE, "kind": "smiles"})
    assert g.status_code == 200
    assert g.json()["prediction"]["score_kind"] == "none"
    assert g.json()["reliability"]["badge"] == "dont_use"

    e = client.post("/predict/embeddings",
                    json={"text": "KVFGRCELAAAMKRHGLDNYRGYSLGNWVCAAKFESNFNTQATNRNTDGSTDYGILQINSR", "kind": "protein"})
    assert e.status_code == 200
    ep = e.json()["prediction"]
    assert ep["extra"]["dim"] == 768
    assert e.json()["reliability"]["badge"] == "split"
