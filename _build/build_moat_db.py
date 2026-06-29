"""
_build/build_moat_db.py — Parquet → SQLite moat ingest (WO-5 dual-rank fix).

Streams the 38.4M-row CNS DFP parquet through bounded per-query heapq heaps
(size K, two per partition) to produce top-K similar + top-K opposite neighbour
rows per perturbation PER REF_TYPE using a DUAL-RANK union approach, then writes
them to a SQLite database at SAPPHIRE_MOAT_DB.

Dual-rank union: a candidate survives if rank_cosine <= K OR rank_euclidean <= K.
The final output record carries rank_cosine, rank_euclidean, and union_rank
(= rank_cosine + rank_euclidean) so the client can order by union_rank.

Environment variables:
    MOAT_PARQUET      Path to the source parquet (default: Loka path below)
    SAPPHIRE_MOAT_DB  Path to the output SQLite file (default: RohanOnly/moat/moat.sqlite)
    MOAT_K            Top-K neighbours per effect per query per ref_type (default: 50)
    MOAT_BATCH_LOG    Log progress every N batches (default: 100)

NOTE (data boundary): internal cosine/euclidean distances used in reasoning only
— never sent to any external tool.

Pure, testable function (importable without pyarrow):
    topk_neighbors(rows, k) -> list[dict]
        rows: iterable of dicts with keys:
              query, query_type, ref, ref_type, ref_dose, cosine, euclidean,
              direction ('Original'|'Antipodal')
        k: int
        Returns flat list of neighbour records, each:
              query(UPPER), query_type, ref, ref_type, ref_dose,
              effect, rank_cosine, rank_euclidean, union_rank, cosine, euclidean
        Direction semantics:
              similar  = rows where direction == 'Original'
              opposite = rows where direction == 'Antipodal'
        Grouping: per (query, effect, ref_type) — genes and compounds get
              separate top-K lists so compounds are never crowded out by genes.
        Survival: rank_cosine <= k OR rank_euclidean <= k
        Rank semantics:
              rank_cosine    = 1-based rank by cosine ASC within the cosine top-K
              rank_euclidean = 1-based rank by euclidean ASC within the euclidean top-K
              K+1 sentinel   = "not in top-K for that metric"
              union_rank     = rank_cosine + rank_euclidean (sort key, lower is better)

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
    / "Desktop/Projects/Quiver"
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
    Dual-rank top-K neighbour extraction, per (effect, ref_type).

    Partitions rows by (query_UPPER, effect, ref_type), excluding self-pairs.
    For each partition:
      - cosine top-K  = k rows with smallest cosine (tiebreak: ref asc)
      - euclidean top-K = k rows with smallest euclidean (tiebreak: ref asc)
      - A candidate survives if it appears in EITHER list (union).

    Rank semantics within each partition:
      rank_cosine    = 1-based position in cosine top-K (k+1 sentinel if absent)
      rank_euclidean = 1-based position in euclidean top-K (k+1 sentinel if absent)
      union_rank     = rank_cosine + rank_euclidean  (sort key, ascending)

    Output is sorted by (union_rank ASC, ref ASC) within each partition.
    Partitions are emitted in (query, effect, ref_type) alphabetical order.

    The 'direction' key is consumed internally and does NOT appear in output records.

    Args:
        rows: iterable of dicts with keys:
              query, query_type, ref, ref_type, ref_dose, cosine, euclidean,
              direction ('Original'|'Antipodal')
        k:    number of neighbours per metric per partition

    Returns:
        Flat list of dicts, each:
            query (UPPERCASE), query_type, ref, ref_type, ref_dose,
            effect, rank_cosine, rank_euclidean, union_rank, cosine, euclidean
    """
    # Partition rows by (q_upper, effect, ref_type), excluding self-pairs
    partitions: dict[tuple[str, str, str], list[dict]] = {}

    for row in rows:
        q_upper = str(row["query"]).upper()
        ref_val = str(row["ref"])

        # Exclude self-pairs (case-insensitive)
        if ref_val.upper() == q_upper:
            continue

        ref_type_val = str(row.get("ref_type", ""))
        direction    = str(row.get("direction", "Original"))
        effect       = "opposite" if direction == "Antipodal" else "similar"
        key          = (q_upper, effect, ref_type_val)

        if key not in partitions:
            partitions[key] = []
        partitions[key].append(row)

    # Process each partition with dual-rank union
    result: list[dict] = []

    for key in sorted(partitions):
        q_upper, effect, ref_type_val = key
        rows_p = partitions[key]

        # ── cosine top-K: k smallest cosines (tiebreak: ref asc) ──────────────
        cos_sorted = sorted(rows_p, key=lambda r: (float(r["cosine"]), str(r["ref"])))
        cos_top_k  = cos_sorted[:k]
        cos_rank_map: dict[str, int] = {
            str(r["ref"]): rank for rank, r in enumerate(cos_top_k, 1)
        }

        # ── euclidean top-K: k smallest euclideans (tiebreak: ref asc) ────────
        euc_sorted = sorted(rows_p, key=lambda r: (float(r["euclidean"]), str(r["ref"])))
        euc_top_k  = euc_sorted[:k]
        euc_rank_map: dict[str, int] = {
            str(r["ref"]): rank for rank, r in enumerate(euc_top_k, 1)
        }

        # ── union of refs that appear in at least one top-K ───────────────────
        all_refs = set(cos_rank_map) | set(euc_rank_map)

        # ref → row lookup (last occurrence if duplicate refs — refs should be unique)
        row_by_ref: dict[str, dict] = {str(r["ref"]): r for r in rows_p}

        # ── build and sort records by union_rank ───────────────────────────────
        recs: list[dict] = []
        for ref in all_refs:
            rank_cosine    = cos_rank_map.get(ref, k + 1)
            rank_euclidean = euc_rank_map.get(ref, k + 1)
            union_rank     = rank_cosine + rank_euclidean
            row            = row_by_ref[ref]
            recs.append({
                "query":         q_upper,
                "query_type":    str(row.get("query_type", "")),
                "ref":           ref,
                "ref_type":      ref_type_val,
                "ref_dose":      row.get("ref_dose", ""),
                "effect":        effect,
                "rank_cosine":   rank_cosine,
                "rank_euclidean": rank_euclidean,
                "union_rank":    union_rank,
                "cosine":        float(row["cosine"]),
                "euclidean":     float(row["euclidean"]),
            })

        recs.sort(key=lambda r: (r["union_rank"], r["ref"]))
        result.extend(recs)

    return result


# ── streaming main (pyarrow import is here only) ───────────────────────────────

def main() -> None:
    """
    Stream the parquet, build bounded dual-rank per-query heaps, write to SQLite.

    Dual-rank union: two heaps per partition (q_upper, effect, ref_type):
      cos_heap: max-heap keeping K smallest cosines
        entry: (-cosine, euclidean, ref, qt, rt, rd)
      euc_heap: max-heap keeping K smallest euclideans
        entry: (-euclidean, cosine, ref, qt, rt, rd)

    A candidate survives if rank_cosine <= K OR rank_euclidean <= K.

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

    # ── per-partition bounded dual heaps ──────────────────────────────────────
    # Partition key: (q_upper, effect_str, ref_type_str)
    #   effect_str = 'opposite' if direction == 'Antipodal' else 'similar'
    #
    # cos_heaps[key]: max-heap keeping K smallest cosines
    #   entry: (-cosine, euclidean, ref, qt, rt, rd)
    #   heappop evicts the LARGEST cosine (= least similar / least opposite)
    #
    # euc_heaps[key]: max-heap keeping K smallest euclideans
    #   entry: (-euclidean, cosine, ref, qt, rt, rd)
    #   heappop evicts the LARGEST euclidean
    cos_heaps: dict[tuple[str, str, str], list] = {}
    euc_heaps: dict[tuple[str, str, str], list] = {}
    n_rows_seen    = 0
    n_self_excluded = 0

    print("[build_moat_db] streaming parquet ...")
    dataset = ds.dataset(str(parquet_path), format="parquet")
    columns = list(_COL_MAP.keys())

    batch_num = 0
    for batch in dataset.to_batches(columns=columns, batch_size=65_536):
        batch_num += 1
        if batch_num % BATCH_LOG == 0:
            print(f"  batch {batch_num:,}  rows_seen={n_rows_seen:,}  partitions={len(cos_heaps):,}")

        q_names  = batch.column("query_perturbationName").to_pylist()
        q_types  = batch.column("query_perturbationType").to_pylist()
        q_dirs   = batch.column("query_perturbationDirection").to_pylist()
        r_names  = batch.column("ref_perturbationName").to_pylist()
        r_types  = batch.column("ref_perturbationType").to_pylist()
        r_doses  = batch.column("ref_perturbationDose").to_pylist()
        cosines  = batch.column("cosine_distance").to_pylist()
        euclids  = batch.column("euclidean_distance").to_pylist()

        for i in range(len(q_names)):
            n_rows_seen += 1
            q_upper = str(q_names[i]).upper() if q_names[i] is not None else ""
            ref_val = str(r_names[i]) if r_names[i] is not None else ""

            if ref_val.upper() == q_upper:
                n_self_excluded += 1
                continue

            direction      = str(q_dirs[i]) if q_dirs[i] is not None else "Original"
            cosine_val     = float(cosines[i]) if cosines[i] is not None else 0.0
            euclidean_val  = float(euclids[i]) if euclids[i] is not None else 0.0
            ref_str        = ref_val
            ref_type_str   = str(r_types[i] or "")
            qt             = str(q_types[i] or "")
            rt             = ref_type_str
            rd             = str(r_doses[i] or "")
            effect_str     = "opposite" if direction == "Antipodal" else "similar"
            heap_key       = (q_upper, effect_str, ref_type_str)

            # cos_heap: keeps K smallest cosines
            # entry: (-cosine, euclidean, ref, qt, rt, rd)
            cos_entry = (-cosine_val, euclidean_val, ref_str, qt, rt, rd)
            if heap_key not in cos_heaps:
                cos_heaps[heap_key] = []
            heapq.heappush(cos_heaps[heap_key], cos_entry)
            if len(cos_heaps[heap_key]) > K:
                heapq.heappop(cos_heaps[heap_key])

            # euc_heap: keeps K smallest euclideans
            # entry: (-euclidean, cosine, ref, qt, rt, rd)
            euc_entry = (-euclidean_val, cosine_val, ref_str, qt, rt, rd)
            if heap_key not in euc_heaps:
                euc_heaps[heap_key] = []
            heapq.heappush(euc_heaps[heap_key], euc_entry)
            if len(euc_heaps[heap_key]) > K:
                heapq.heappop(euc_heaps[heap_key])

    all_heap_keys = sorted(set(cos_heaps) | set(euc_heaps))
    n_queries = len({k[0] for k in all_heap_keys})
    print(f"[build_moat_db] done streaming: {n_rows_seen:,} rows, {n_self_excluded:,} self-excluded, {n_queries:,} queries")

    # ── drain heaps → flat records ─────────────────────────────────────────────
    print("[build_moat_db] draining heaps and writing SQLite ...")

    records: list[tuple] = []
    for heap_key in all_heap_keys:
        q_upper, effect_str, ref_type_str = heap_key

        # ── cosine heap: sorted by cosine ASC, euclidean ASC, ref ASC ─────────
        # cos_entry: (-cosine, euclidean, ref, qt, rt, rd)
        # -e[0] = cosine ASC, e[1] = euclidean ASC, e[2] = ref ASC
        cos_items  = cos_heaps.get(heap_key, [])
        cos_sorted = sorted(cos_items, key=lambda e: (-e[0], e[1], e[2]))
        cos_rank_map: dict[str, int] = {
            e[2]: rank for rank, e in enumerate(cos_sorted, 1)
        }

        # ── euclidean heap: sorted by euclidean ASC, cosine ASC, ref ASC ──────
        # euc_entry: (-euclidean, cosine, ref, qt, rt, rd)
        # -e[0] = euclidean ASC, e[1] = cosine ASC, e[2] = ref ASC
        euc_items  = euc_heaps.get(heap_key, [])
        euc_sorted = sorted(euc_items, key=lambda e: (-e[0], e[1], e[2]))
        euc_rank_map: dict[str, int] = {
            e[2]: rank for rank, e in enumerate(euc_sorted, 1)
        }

        # ── ref → (cosine, euclidean, qt, rt, rd) lookup from both heaps ──────
        ref_data: dict[str, tuple] = {}
        for e in cos_items:
            ref = e[2]
            cosv = -e[0]
            eucv = e[1]
            qt, rt, rd = e[3], e[4], e[5]
            ref_data[ref] = (cosv, eucv, qt, rt, rd)
        for e in euc_items:
            ref = e[2]
            eucv = -e[0]
            cosv = e[1]
            qt, rt, rd = e[3], e[4], e[5]
            if ref not in ref_data:
                ref_data[ref] = (cosv, eucv, qt, rt, rd)

        # ── union and dual-rank ───────────────────────────────────────────────
        all_refs = set(cos_rank_map) | set(euc_rank_map)
        recs: list[tuple] = []
        for ref in all_refs:
            rank_cosine    = cos_rank_map.get(ref, K + 1)
            rank_euclidean = euc_rank_map.get(ref, K + 1)
            union_rank     = rank_cosine + rank_euclidean
            cosv, eucv, qt, rt, rd = ref_data[ref]
            recs.append((
                union_rank, ref,          # sort keys (not stored)
                q_upper, qt, ref, rt, rd, effect_str,
                rank_cosine, rank_euclidean, union_rank, cosv, eucv,
            ))

        recs.sort(key=lambda r: (r[0], r[1]))  # union_rank ASC, ref ASC
        for rec in recs:
            # Strip the two sort-key prefix values
            records.append(rec[2:])

    # ── write SQLite ───────────────────────────────────────────────────────────
    con = sqlite3.connect(str(db_path))
    try:
        con.execute("DROP TABLE IF EXISTS neighbors")
        con.execute("DROP TABLE IF EXISTS moat_meta")
        con.execute("DROP INDEX IF EXISTS ix_neighbors_q")
        con.execute("""
            CREATE TABLE neighbors (
                query          TEXT NOT NULL,
                query_type     TEXT,
                ref            TEXT NOT NULL,
                ref_type       TEXT,
                ref_dose       TEXT,
                effect         TEXT NOT NULL,
                rank_cosine    INTEGER NOT NULL,
                rank_euclidean INTEGER NOT NULL,
                union_rank     INTEGER NOT NULL,
                cosine         REAL,
                euclidean      REAL
            )
        """)
        con.executemany(
            "INSERT INTO neighbors VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            records,
        )
        con.execute("CREATE INDEX ix_neighbors_q ON neighbors(query, effect, ref_type)")
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

    print(f"[build_moat_db] wrote {len(records):,} neighbor rows ({n_queries:,} queries x2 effects x ref_types) → {db_path}")

    # ── sanity: print top-5 similar + opposite + opposite genes for TSC2 ──────
    _print_sanity(str(db_path), "TSC2")


def _print_sanity(db_path: str, query: str) -> None:
    """Print top-5 similar and opposite for the given query as a sanity check.

    Ordered by union_rank (dual-rank metric). Also prints top-5 opposite GENE
    results for the TSC2 gene-rescue sanity check.
    """
    try:
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row
        print(f"\n── Sanity: {query} similar (top-5, all types) ──")
        for row in con.execute(
            "SELECT rank_cosine, rank_euclidean, union_rank, ref, ref_type, cosine "
            "FROM neighbors WHERE query=? AND effect='similar' "
            "ORDER BY union_rank LIMIT 5",
            (query.upper(),),
        ):
            print(
                f"  union={row['union_rank']:2d} (cos_r={row['rank_cosine']}, euc_r={row['rank_euclidean']}). "
                f"{row['ref']:<30s}  cosine={row['cosine']:.4f}  type={row['ref_type']}"
            )
        print(f"\n── Sanity: {query} opposite (top-5, all types) ──")
        for row in con.execute(
            "SELECT rank_cosine, rank_euclidean, union_rank, ref, ref_type, cosine "
            "FROM neighbors WHERE query=? AND effect='opposite' "
            "ORDER BY union_rank LIMIT 5",
            (query.upper(),),
        ):
            print(
                f"  union={row['union_rank']:2d} (cos_r={row['rank_cosine']}, euc_r={row['rank_euclidean']}). "
                f"{row['ref']:<30s}  cosine={row['cosine']:.4f}  type={row['ref_type']}"
            )
        print(f"\n── Sanity: {query} opposite GENES (top-5, rescue) ──")
        for row in con.execute(
            "SELECT rank_cosine, rank_euclidean, union_rank, ref, ref_type, cosine "
            "FROM neighbors WHERE query=? AND effect='opposite' AND ref_type='gene' "
            "ORDER BY union_rank LIMIT 5",
            (query.upper(),),
        ):
            print(
                f"  union={row['union_rank']:2d} (cos_r={row['rank_cosine']}, euc_r={row['rank_euclidean']}). "
                f"{row['ref']:<30s}  cosine={row['cosine']:.4f}  type={row['ref_type']}"
            )
        con.close()
    except Exception as exc:
        print(f"[sanity] error: {exc}")


if __name__ == "__main__":
    main()
