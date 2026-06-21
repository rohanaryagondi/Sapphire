"""Stub-mode smoke tests for the Quiver Capability Explorer.

These assert the CONTRACT's API shapes (not a specific backend implementation) and
run entirely in stub mode: no AWS endpoint, no GPU, no model weights. Every track's
expected ``score_kind`` is read from ``tracks.json`` so the tests stay locked to the
data contract.

See ``conftest.py`` for the TestClient fixture (``client``): isolated temp history,
``EXPLORER_AWS_ENDPOINT`` cleared, repo root on ``sys.path``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

EXPLORER_DIR = Path(__file__).resolve().parents[1]
TRACKS = json.loads((EXPLORER_DIR / "tracks.json").read_text())
TRACK_LIST = TRACKS["tracks"]
TRACK_IDS = [t["id"] for t in TRACK_LIST]
SCORE_KIND = {t["id"]: t["stub_prediction"]["score_kind"] for t in TRACK_LIST}
BATCH_TRACKS = [t["id"] for t in TRACK_LIST if "batch" in t]


# --------------------------------------------------------------------------- meta

def test_meta_is_stubbed(client):
    """No AWS endpoint configured → /api/meta must report stubbed True."""
    r = client.get("/api/meta")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stubbed"] is True
    # Meta carries the framing the header/banner render from.
    for key in ("title", "subtitle", "banner", "badges"):
        assert key in body
    assert isinstance(body["badges"], dict) and body["badges"]


# ------------------------------------------------------------------------- tracks

def test_tracks_returns_all(client):
    r = client.get("/api/tracks")
    assert r.status_code == 200, r.text
    tracks = r.json()["tracks"]
    assert len(tracks) == 9
    assert {t["id"] for t in tracks} == set(TRACK_IDS)
    # The list is for rendering tabs/report rows — should not ship the heavy stub.
    for t in tracks:
        assert "stub_prediction" not in t


def test_report_covers_all_tracks(client):
    r = client.get("/api/report")
    assert r.status_code == 200, r.text
    rows = r.json()["tracks"]
    assert len(rows) == 9
    assert {row["n"] for row in rows} == set(range(1, 10))
    for row in rows:
        # The report is the centerpiece "model per track + how it performs" page.
        assert row["best_model"]
        assert row["badge"] in TRACKS["_meta"]["badges"]


# ------------------------------------------------------------------------ predict

def _example_payload(track_id: str) -> dict:
    """The track's canonical example inputs (what 'Load example' prefills)."""
    track = next(t for t in TRACK_LIST if t["id"] == track_id)
    return dict(track.get("example", {}))


@pytest.mark.parametrize("track_id", TRACK_IDS)
def test_predict_each_track_stubbed(client, track_id):
    """Every track's predict route: 200, stubbed True, score_kind matches tracks.json."""
    r = client.post(f"/api/predict/{track_id}", json=_example_payload(track_id))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stubbed"] is True
    assert body["track"] == track_id
    pred = body["prediction"]
    assert pred["score_kind"] == SCORE_KIND[track_id]
    # The verdict travels with every result.
    assert body["verdict"]["badge"] in TRACKS["_meta"]["badges"]




# -------------------------------------------------------------------------- batch

def test_bbbp_batch_ranks_rows(client):
    """A batch POST for bbbp returns ranked rows (best-first)."""
    assert "bbbp" in BATCH_TRACKS  # guard: bbbp is batch-enabled in tracks.json
    rows = [
        {"smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"},   # caffeine
        {"smiles": "CC(=O)OC1=CC=CC=C1C(=O)O"},         # aspirin
        {"smiles": "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O"},    # ibuprofen
    ]
    r = client.post("/api/predict/bbbp/batch", json={"rows": rows})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["track"] == "bbbp"
    out = body["rows"]
    assert len(out) == len(rows)
    # Every successful row carries a rank; ranks are 1..N best-first and contiguous.
    ranks = [row["rank"] for row in out if row.get("error") is None]
    assert ranks == sorted(ranks)
    assert ranks[0] == 1
    # Each ranked row echoes its inputs back for re-load.
    for row in out:
        assert "inputs" in row


# ------------------------------------------------------------------------ history

def test_history_grows_then_clears(client):
    """History is empty, grows after a predict, and DELETE clears it."""
    before = client.get("/api/history")
    assert before.status_code == 200, before.text
    n_before = len(before.json()["records"])

    p = client.post("/api/predict/bbbp", json=_example_payload("bbbp"))
    assert p.status_code == 200, p.text

    after = client.get("/api/history")
    assert after.status_code == 200, after.text
    n_after = len(after.json()["records"])
    assert n_after > n_before

    d = client.delete("/api/history")
    assert d.status_code == 200, d.text

    cleared = client.get("/api/history")
    assert cleared.status_code == 200, cleared.text
    assert len(cleared.json()["records"]) == 0


def test_history_filter_by_track(client):
    """The ?track= filter only returns that track's runs."""
    client.delete("/api/history")
    client.post("/api/predict/bbbp", json=_example_payload("bbbp"))
    client.post("/api/predict/toxicity", json=_example_payload("toxicity"))

    r = client.get("/api/history", params={"track": "bbbp"})
    assert r.status_code == 200, r.text
    recs = r.json()["records"]
    assert recs, "expected at least one bbbp history record"
    for rec in recs:
        assert rec.get("task") == "bbbp" or rec.get("track") == "bbbp"


# ---------------------------------------------------------------------------- doc

def test_doc_serves_known_results_md(client):
    """/doc serves a real results markdown (a verdict 'source:' citation)."""
    r = client.get("/doc/results/bbbp_characterization.md")
    assert r.status_code == 200, r.text
    assert r.text.strip()  # non-empty markdown


@pytest.mark.parametrize(
    "path",
    [
        "/doc/../../etc/passwd",          # raw — client may normalize this away
        "/doc/%2e%2e/%2e%2e/etc/passwd",  # encoded — survives to the route handler
        "/doc/results/../../etc/passwd",  # escape from inside an allowed root
    ],
)
def test_doc_rejects_path_traversal(client, path):
    """/doc must refuse to escape results/ + docs/, however the dots are encoded."""
    r = client.get(path)
    assert r.status_code in (403, 404), r.text
    # Whatever the status, the response must never contain /etc/passwd contents.
    assert "root:" not in r.text
