"""
_build/build_moat_db.py — Parquet → SQLite moat ingest (Task 3).

Streams the 38.4M-row CNS DFP parquet through bounded per-query heapq heaps
(size K) to produce the top-K similar + top-K opposite neighbor rows per
perturbation, then writes them to a SQLite database at SAPPHIRE_MOAT_DB.

Environment variables:
    MOAT_PARQUET      Path to the source parquet (default: Loka path below)
    SAPPHIRE_MOAT_DB  Path to the output SQLite file (default: RohanOnly/moat/moat.sqlite)
    MOAT_K            Top-K neighbours per effect per query (default: 50)
    MOAT_BATCH_LOG    Log progress every N batches (default: 100)

Pure, testable function (importable without pyarrow):
    topk_neighbors(rows, k) -> list[dict]
        rows: iterable of dicts with keys:
              query, query_type, ref, ref_type, ref_dose, cosine, euclidean
        k: int
        Returns flat list of neighbour records, each:
              query(UPPER), query_type, ref, ref_type, ref_dose,
              effect, rank, cosine, euclidean

NOTE: pyarrow is imported ONLY inside main() — topk_neighbors has zero
third-party dependencies so it can be loaded by tests without pyarrow installed.
"""

from __future__ import annotations

import heapq
import os
import sqlite3
from pathlib import Path
from typing import Iterable

# ── repo-relative defaults ─────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_DB = _REPO_ROOT / "RohanOnly" / "moat" / "moat.sqlite"
_DEFAULT_PARQUET = (
    Path.home()
    / "Library/CloudStorage/OneDrive-YaleUniversity/Career/Quiver/Sapphire"
    / "Loka - Shared Folder/Data/CNS_DFP_distance_20251215.parquet"
)

# ── Parquet column → internal field mapping ────────────────────────────────────
_COL_MAP = {
    "query_perturbationName":  "query",
    "query_perturbationType":  "query_type",
    "ref_perturbationName":    "ref",
    "ref_perturbationType":    "ref_type",
    "ref_perturbationDose":    "ref_dose",
    "cosine_distance":         "cosine",
    "euclidean_distance":      "euclidean",
}


# ── pure, testable core ────────────────────────────────────────────────────────

def topk_neighbors(rows: Iterable[dict], k: int) -> list[dict]:
    """
    Group rows by query, exclude self-pairs, and return for each query:
      - k smallest-cosine records (effect='similar', rank 1..k ascending by cosine)
      - k largest-cosine records  (effect='opposite', rank 1..k descending by cosine)

    Tie-break: when cosines are equal, sort by ref name ascending (deterministic).

    This function is unbounded-memory (collects all candidates per query, then
    sorts and slices). For streaming 38M rows with bounded memory, use main()
    which maintains per-query bounded heapq heaps with correct tie-break eviction.

    Args:
        rows: iterable of dicts with keys:
              query, query_type, ref, ref_type, ref_dose, cosine, euclidean
        k:    number of neighbours per effect per query

    Returns:
        Flat list of dicts, each:
            query (UPPERCASE), query_type, ref, ref_type, ref_dose,
            effect, rank, cosine, euclidean
    """
    # Collect all non-self candidates per query
    buckets: dict[str, list[dict]] = {}

    for row in rows:
        q_upper = str(row["query"]).upper()
        ref_val = str(row["ref"])

        # Exclude self-pairs (case-insensitive comparison)
        if ref_val.upper() == q_upper:
            continue

        if q_upper not in buckets:
            buckets[q_upper] = []
        buckets[q_upper].append(row)

    result: list[dict] = []

    for q_upper in sorted(buckets):
        candidates = buckets[q_upper]

        # ── similar: k smallest cosines, tie-break ref ascending ────────────
        sim_sorted = sorted(candidates, key=lambda r: (float(r["cosine"]), str(r["ref"])))
        for rank, row in enumerate(sim_sorted[:k], start=1):
            result.append(_make_record(q_upper, row, "similar", rank))

        # ── opposite: k largest cosines, rank 1=largest; tie-break ref asc ──
        opp_sorted = sorted(candidates, key=lambda r: (-float(r["cosine"]), str(r["ref"])))
        for rank, row in enumerate(opp_sorted[:k], start=1):
            result.append(_make_record(q_upper, row, "opposite", rank))

    return result


def _make_record(q_upper: str, row: dict, effect: str, rank: int) -> dict:
    """Build a single output record from a raw row + effect/rank."""
    return {
        "query":      q_upper,
        "query_type": row.get("query_type", ""),
        "ref":        row["ref"],
        "ref_type":   row.get("ref_type", ""),
        "ref_dose":   row.get("ref_dose", ""),
        "effect":     effect,
        "rank":       rank,
        "cosine":     float(row["cosine"]),
        "euclidean":  float(row["euclidean"]),
    }


# ── streaming main (pyarrow import is here only) ───────────────────────────────

def main() -> None:
    """
    Stream the parquet, build bounded per-query heaps, write to SQLite.
    Env vars: MOAT_PARQUET, SAPPHIRE_MOAT_DB, MOAT_K, MOAT_BATCH_LOG.
    """
    import pyarrow.dataset as ds  # noqa: PLC0415 — intentional late import
    from datetime import datetime

    parquet_path = Path(os.environ.get("MOAT_PARQUET", str(_DEFAULT_PARQUET)))
    db_path      = Path(os.environ.get("SAPPHIRE_MOAT_DB", str(_DEFAULT_DB)))
    K            = int(os.environ.get("MOAT_K", "50"))
    BATCH_LOG    = int(os.environ.get("MOAT_BATCH_LOG", "100"))

    print(f"[build_moat_db] source parquet : {parquet_path}")
    print(f"[build_moat_db] output db      : {db_path}")
    print(f"[build_moat_db] K              : {K}")

    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet not found: {parquet_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    # ── per-query bounded heaps ────────────────────────────────────────────────
    # sim_heaps[q] = min-heap of (-cosine, ref, cosine, euclidean, query_type, ref_type, ref_dose)
    # opp_heaps[q] = min-heap of (cosine,  ref, cosine, euclidean, query_type, ref_type, ref_dose)
    sim_heaps: dict[str, list] = {}
    opp_heaps: dict[str, list] = {}
    n_rows_seen = 0
    n_self_excluded = 0

    print("[build_moat_db] streaming parquet ...")
    dataset = ds.dataset(str(parquet_path), format="parquet")
    columns = list(_COL_MAP.keys())

    batch_num = 0
    for batch in dataset.to_batches(columns=columns, batch_size=65_536):
        batch_num += 1
        if batch_num % BATCH_LOG == 0:
            print(f"  batch {batch_num:,}  rows_seen={n_rows_seen:,}  queries={len(sim_heaps):,}")

        # Convert batch to Python lists for speed
        q_names   = batch.column("query_perturbationName").to_pylist()
        q_types   = batch.column("query_perturbationType").to_pylist()
        r_names   = batch.column("ref_perturbationName").to_pylist()
        r_types   = batch.column("ref_perturbationType").to_pylist()
        r_doses   = batch.column("ref_perturbationDose").to_pylist()
        cosines   = batch.column("cosine_distance").to_pylist()
        euclids   = batch.column("euclidean_distance").to_pylist()

        for i in range(len(q_names)):
            n_rows_seen += 1
            q_upper = str(q_names[i]).upper() if q_names[i] is not None else ""
            ref_val = str(r_names[i]) if r_names[i] is not None else ""

            if ref_val.upper() == q_upper:
                n_self_excluded += 1
                continue

            cosine_val   = float(cosines[i])  if cosines[i]  is not None else 0.0
            euclidean_val= float(euclids[i])  if euclids[i]  is not None else 0.0
            ref_str      = ref_val
            payload      = (str(q_types[i] or ""), str(r_types[i] or ""), str(r_doses[i] or ""), cosine_val, euclidean_val)

            # similar: max-heap on cosine → store (-cosine, ref, payload)
            entry_sim = (-cosine_val, ref_str) + payload
            if q_upper not in sim_heaps:
                sim_heaps[q_upper] = []
            heapq.heappush(sim_heaps[q_upper], entry_sim)
            if len(sim_heaps[q_upper]) > K:
                heapq.heappop(sim_heaps[q_upper])

            # opposite: min-heap on cosine → store (cosine, ref, payload)
            entry_opp = (cosine_val, ref_str) + payload
            if q_upper not in opp_heaps:
                opp_heaps[q_upper] = []
            heapq.heappush(opp_heaps[q_upper], entry_opp)
            if len(opp_heaps[q_upper]) > K:
                heapq.heappop(opp_heaps[q_upper])

    n_queries = len(sim_heaps)
    print(f"[build_moat_db] done streaming: {n_rows_seen:,} rows, {n_self_excluded:,} self-excluded, {n_queries:,} queries")

    # ── drain heaps → flat records ─────────────────────────────────────────────
    print("[build_moat_db] draining heaps and writing SQLite ...")

    all_queries = sorted(set(sim_heaps) | set(opp_heaps))
    records: list[tuple] = []
    for q_upper in all_queries:
        sim_items = sim_heaps.get(q_upper, [])
        # sort: ascending cosine (-neg_cosine), then ref ascending
        sim_sorted = sorted(sim_items, key=lambda t: (-t[0], t[1]))
        for rank, entry in enumerate(sim_sorted, start=1):
            neg_c, ref, qt, rt, rd, cosv, eucv = entry
            records.append((q_upper, qt, ref, rt, rd, "similar", rank, cosv, eucv))

        opp_items = opp_heaps.get(q_upper, [])
        # sort: descending cosine, then ref ascending
        opp_sorted = sorted(opp_items, key=lambda t: (-t[0], t[1]))
        for rank, entry in enumerate(opp_sorted, start=1):
            cosv, ref, qt, rt, rd, _c2, eucv = entry
            records.append((q_upper, qt, ref, rt, rd, "opposite", rank, cosv, eucv))

    # ── write SQLite ───────────────────────────────────────────────────────────
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DROP TABLE IF EXISTS neighbors")
        con.execute("DROP TABLE IF EXISTS moat_meta")
        con.execute("DROP INDEX IF EXISTS ix_neighbors_q")
        con.execute("""
            CREATE TABLE neighbors (
                query       TEXT NOT NULL,
                query_type  TEXT,
                ref         TEXT NOT NULL,
                ref_type    TEXT,
                ref_dose    TEXT,
                effect      TEXT NOT NULL,
                rank        INTEGER NOT NULL,
                cosine      REAL,
                euclidean   REAL
            )
        """)
        con.executemany(
            "INSERT INTO neighbors VALUES (?,?,?,?,?,?,?,?,?)",
            records,
        )
        con.execute("CREATE INDEX ix_neighbors_q ON neighbors(query, effect)")
        con.execute("""
            CREATE TABLE moat_meta (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        meta_rows = [
            ("source",    str(parquet_path)),
            ("built_at",  datetime.now().isoformat()),
            ("k",         str(K)),
            ("n_queries", str(n_queries)),
            ("n_rows",    str(len(records))),
        ]
        con.executemany("INSERT INTO moat_meta VALUES (?,?)", meta_rows)
        con.commit()
    finally:
        con.close()

    print(f"[build_moat_db] wrote {len(records):,} neighbor rows ({n_queries:,} queries x2 effects) → {db_path}")

    # ── sanity: print top-5 similar + opposite for TSC2 ───────────────────────
    _print_sanity(str(db_path), "TSC2")


def _print_sanity(db_path: str, query: str) -> None:
    """Print top-5 similar and opposite for the given query as a sanity check."""
    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        print(f"\n── Sanity: {query} similar (top-5) ──")
        for row in con.execute(
            "SELECT rank, ref, ref_type, cosine FROM neighbors WHERE query=? AND effect='similar' ORDER BY rank LIMIT 5",
            (query.upper(),),
        ):
            print(f"  {row['rank']:2d}. {row['ref']:<30s}  cosine={row['cosine']:.4f}  type={row['ref_type']}")
        print(f"\n── Sanity: {query} opposite (top-5) ──")
        for row in con.execute(
            "SELECT rank, ref, ref_type, cosine FROM neighbors WHERE query=? AND effect='opposite' ORDER BY rank LIMIT 5",
            (query.upper(),),
        ):
            print(f"  {row['rank']:2d}. {row['ref']:<30s}  cosine={row['cosine']:.4f}  type={row['ref_type']}")
        con.close()
    except Exception as exc:
        print(f"[sanity] error: {exc}")


if __name__ == "__main__":
    main()
