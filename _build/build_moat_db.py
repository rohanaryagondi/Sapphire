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
              query, query_type, ref, ref_type, ref_dose, cosine, euclidean,
              direction ('Original'|'Antipodal')
        k: int
        Returns flat list of neighbour records, each:
              query(UPPER), query_type, ref, ref_type, ref_dose,
              effect, rank, cosine, euclidean
        Direction semantics:
              similar  = k smallest-cosine rows with direction=='Original'
              opposite = k smallest-cosine rows with direction=='Antipodal'

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
    "query_perturbationName":      "query",
    "query_perturbationType":      "query_type",
    "query_perturbationDirection": "direction",
    "ref_perturbationName":        "ref",
    "ref_perturbationType":        "ref_type",
    "ref_perturbationDose":        "ref_dose",
    "cosine_distance":             "cosine",
    "euclidean_distance":          "euclidean",
}


# ── pure, testable core ────────────────────────────────────────────────────────

def topk_neighbors(rows: Iterable[dict], k: int) -> list[dict]:
    """
    Direction-aware top-K neighbour extraction.

    Group rows by query (uppercased), exclude self-pairs, then for each query:
      - similar  = k smallest-cosine rows where direction == 'Original'
                   ranked 1..k ascending by cosine (tie-break: ref ascending)
      - opposite = k smallest-cosine rows where direction == 'Antipodal'
                   ranked 1..k ascending by cosine (tie-break: ref ascending)

    The 'direction' key is consumed internally and does NOT appear in output records.

    Args:
        rows: iterable of dicts with keys:
              query, query_type, ref, ref_type, ref_dose, cosine, euclidean,
              direction ('Original'|'Antipodal')
        k:    number of neighbours per effect per query

    Returns:
        Flat list of dicts, each:
            query (UPPERCASE), query_type, ref, ref_type, ref_dose,
            effect, rank, cosine, euclidean
    """
    # Collect non-self candidates split by direction
    # sim_buckets[q] = Original rows; opp_buckets[q] = Antipodal rows
    sim_buckets: dict[str, list[dict]] = {}
    opp_buckets: dict[str, list[dict]] = {}

    for row in rows:
        q_upper = str(row["query"]).upper()
        ref_val = str(row["ref"])

        # Exclude self-pairs (case-insensitive)
        if ref_val.upper() == q_upper:
            continue

        direction = str(row.get("direction", "Original"))
        if direction == "Antipodal":
            bucket = opp_buckets
        else:
            bucket = sim_buckets

        if q_upper not in bucket:
            bucket[q_upper] = []
        bucket[q_upper].append(row)

    all_queries = sorted(set(sim_buckets) | set(opp_buckets))
    result: list[dict] = []

    for q_upper in all_queries:
        # ── similar: k smallest cosines from Original rows ──────────────────
        sim_cands = sim_buckets.get(q_upper, [])
        sim_sorted = sorted(sim_cands, key=lambda r: (float(r["cosine"]), str(r["ref"])))
        for rank, row in enumerate(sim_sorted[:k], start=1):
            result.append(_make_record(q_upper, row, "similar", rank))

        # ── opposite: k smallest cosines from Antipodal rows ────────────────
        opp_cands = opp_buckets.get(q_upper, [])
        opp_sorted = sorted(opp_cands, key=lambda r: (float(r["cosine"]), str(r["ref"])))
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

    # ── per-query bounded heaps (direction-aware) ──────────────────────────────
    # sim_heaps[q]: Original rows  — keep K smallest-cosine
    #   stored as max-heap of size K via negated key: (-cosine, ref, payload...)
    #   when heap > K, heappop evicts the *largest* cosine (least similar)
    # opp_heaps[q]: Antipodal rows — keep K smallest-cosine (same structure)
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
        q_dirs    = batch.column("query_perturbationDirection").to_pylist()
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

            direction    = str(q_dirs[i]) if q_dirs[i] is not None else "Original"
            cosine_val   = float(cosines[i])  if cosines[i]  is not None else 0.0
            euclidean_val= float(euclids[i])  if euclids[i]  is not None else 0.0
            ref_str      = ref_val
            payload      = (str(q_types[i] or ""), str(r_types[i] or ""), str(r_doses[i] or ""), cosine_val, euclidean_val)

            # Both similar and opposite use a max-heap of size K keyed on cosine
            # so that heappop evicts the largest cosine (keeping K smallest).
            # Entry: (-cosine, ref, ...payload) — Python min-heap on negated cosine.
            entry = (-cosine_val, ref_str) + payload

            if direction == "Antipodal":
                # opposite: k smallest-cosine Antipodal rows
                if q_upper not in opp_heaps:
                    opp_heaps[q_upper] = []
                heapq.heappush(opp_heaps[q_upper], entry)
                if len(opp_heaps[q_upper]) > K:
                    heapq.heappop(opp_heaps[q_upper])
            else:
                # similar: k smallest-cosine Original rows
                if q_upper not in sim_heaps:
                    sim_heaps[q_upper] = []
                heapq.heappush(sim_heaps[q_upper], entry)
                if len(sim_heaps[q_upper]) > K:
                    heapq.heappop(sim_heaps[q_upper])

    n_queries = len(sim_heaps)
    print(f"[build_moat_db] done streaming: {n_rows_seen:,} rows, {n_self_excluded:,} self-excluded, {n_queries:,} queries")

    # ── drain heaps → flat records ─────────────────────────────────────────────
    print("[build_moat_db] draining heaps and writing SQLite ...")

    all_queries = sorted(set(sim_heaps) | set(opp_heaps))
    records: list[tuple] = []
    for q_upper in all_queries:
        # Entry format: (-cosine_val, ref, qt, rt, rd, cosine_val, euclidean_val)
        # t[0] = -cosine_val; to sort by cosine ascending: sort -t[0] ascending (i.e. -(-c) = c asc)
        # tie-break: ref ascending (t[1])

        sim_items = sim_heaps.get(q_upper, [])
        sim_sorted = sorted(sim_items, key=lambda t: (-t[0], t[1]))  # cosine asc, ref asc
        for rank, entry in enumerate(sim_sorted, start=1):
            neg_c, ref, qt, rt, rd, cosv, eucv = entry
            records.append((q_upper, qt, ref, rt, rd, "similar", rank, cosv, eucv))

        opp_items = opp_heaps.get(q_upper, [])
        opp_sorted = sorted(opp_items, key=lambda t: (-t[0], t[1]))  # cosine asc, ref asc
        for rank, entry in enumerate(opp_sorted, start=1):
            neg_c, ref, qt, rt, rd, cosv, eucv = entry
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

    # ── sanity: print top-5 similar (Original) + opposite (Antipodal) for TSC2 ─
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
