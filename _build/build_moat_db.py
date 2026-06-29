"""
_build/build_moat_db.py — Parquet → SQLite moat ingest (WO-5 dual-rank fix, v2 true-global).

Streams the 38.4M-row CNS DFP parquet and accumulates per-partition rows in memory,
then computes TRUE GLOBAL ranks (faithful to Loka's perturbation_similarity_top200
materialized view) before writing to a SQLite database at SAPPHIRE_MOAT_DB.

Dual-rank union: a candidate survives if rank_cosine <= K OR rank_euclidean <= K.
The final output record carries rank_cosine, rank_euclidean, and union_rank
(= rank_cosine + rank_euclidean) so the client can order by union_rank.

True global ranks (Loka faithful):
    ROW_NUMBER() OVER (PARTITION BY query_name, match_effect, ref_type
                       ORDER BY cosine ASC, euclidean ASC, ref ASC)   → rank_cosine
    ROW_NUMBER() OVER (PARTITION BY ...
                       ORDER BY euclidean ASC, cosine ASC, ref ASC)   → rank_euclidean
No K+1 sentinel — every row in the partition gets its true global rank.

Multi-dose deduplication (Loka global_ranking.py faithful):
    When a query name has multiple perturbation IDs (doses), each produces its own
    similarity rows. We aggregate by (query_name, ref_name, effect, ref_type), keeping
    MIN(cosine) and MIN(euclidean) per ref — matching Loka's MIN aggregation approach.

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
        Rank semantics (TRUE global, no sentinel):
              rank_cosine    = 1-based rank by (cosine ASC, euclidean ASC, ref ASC)
                               across ALL rows in the partition
              rank_euclidean = 1-based rank by (euclidean ASC, cosine ASC, ref ASC)
                               across ALL rows in the partition
              union_rank     = rank_cosine + rank_euclidean (sort key, lower is better)

NOTE: pyarrow is imported ONLY inside main() — topk_neighbors has zero
third-party dependencies so it can be loaded by tests without pyarrow installed.
"""

from __future__ import annotations

import os
import sqlite3
import sys
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
      - Computes TRUE global rank_cosine for ALL rows in the partition,
        ordered by (cosine ASC, euclidean ASC, ref ASC).
      - Computes TRUE global rank_euclidean for ALL rows in the partition,
        ordered by (euclidean ASC, cosine ASC, ref ASC).
      - A candidate survives if rank_cosine <= k OR rank_euclidean <= k (union).

    No K+1 sentinel — ranks are the true global 1-based positions.

    Rank semantics within each partition (TRUE global, no sentinel):
      rank_cosine    = 1-based global rank by (cosine ASC, euclidean ASC, ref ASC)
      rank_euclidean = 1-based global rank by (euclidean ASC, cosine ASC, ref ASC)
      union_rank     = rank_cosine + rank_euclidean  (sort key, ascending)

    Output is sorted by (union_rank ASC, ref ASC) within each partition.
    Partitions are emitted in (query, effect, ref_type) alphabetical order.

    The 'direction' key is consumed internally and does NOT appear in output records.

    Args:
        rows: iterable of dicts with keys:
              query, query_type, ref, ref_type, ref_dose, cosine, euclidean,
              direction ('Original'|'Antipodal')
        k:    number of neighbours per metric per partition (survival threshold)

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

    # Process each partition with true global dual-rank union
    result: list[dict] = []

    for key in sorted(partitions):
        q_upper, effect, ref_type_val = key
        rows_p = partitions[key]

        # ── TRUE global rank_cosine: rank ALL rows, tiebreak (cosine, euclidean, ref) ──
        cos_sorted = sorted(
            rows_p,
            key=lambda r: (float(r["cosine"]), float(r["euclidean"]), str(r["ref"])),
        )
        cos_rank_map: dict[str, int] = {
            str(r["ref"]): rank for rank, r in enumerate(cos_sorted, 1)
        }

        # ── TRUE global rank_euclidean: rank ALL rows, tiebreak (euclidean, cosine, ref) ──
        euc_sorted = sorted(
            rows_p,
            key=lambda r: (float(r["euclidean"]), float(r["cosine"]), str(r["ref"])),
        )
        euc_rank_map: dict[str, int] = {
            str(r["ref"]): rank for rank, r in enumerate(euc_sorted, 1)
        }

        # ── union of refs that appear in at least one top-K (survival gate) ───
        all_refs = {
            ref for ref, rc in cos_rank_map.items() if rc <= k
        } | {
            ref for ref, re in euc_rank_map.items() if re <= k
        }

        # ref → row lookup (last occurrence if duplicate refs — refs should be unique)
        row_by_ref: dict[str, dict] = {str(r["ref"]): r for r in rows_p}

        # ── build and sort records by union_rank ───────────────────────────────
        recs: list[dict] = []
        for ref in all_refs:
            rank_cosine    = cos_rank_map[ref]    # true global rank, no sentinel
            rank_euclidean = euc_rank_map[ref]    # true global rank, no sentinel
            union_rank     = rank_cosine + rank_euclidean
            row            = row_by_ref[ref]
            recs.append({
                "query":          q_upper,
                "query_type":     str(row.get("query_type", "")),
                "ref":            ref,
                "ref_type":       ref_type_val,
                "ref_dose":       row.get("ref_dose", ""),
                "effect":         effect,
                "rank_cosine":    rank_cosine,
                "rank_euclidean": rank_euclidean,
                "union_rank":     union_rank,
                "cosine":         float(row["cosine"]),
                "euclidean":      float(row["euclidean"]),
            })

        recs.sort(key=lambda r: (r["union_rank"], r["ref"]))
        result.extend(recs)

    return result


# ── streaming main (pyarrow import is here only) ───────────────────────────────

def main() -> None:
    """
    Stream the parquet, accumulate per-partition rows in memory, compute true
    global dual-rank union, write to SQLite.

    True global ranks (faithful to Loka's perturbation_similarity_top200 view):
      For each partition (q_name, match_effect, ref_type), rank ALL rows by
        (cosine ASC, euclidean ASC, ref ASC)  → rank_cosine
        (euclidean ASC, cosine ASC, ref ASC)  → rank_euclidean
      No K+1 sentinel — all rows get their true 1-based global rank.

    Multi-dose deduplication (faithful to Loka's global_ranking.py MIN approach):
      Per partition, keep MIN(cosine) and MIN(euclidean) per ref_name.
      This correctly handles queries that have multiple perturbation IDs (doses).

    Memory: per-partition dict of ref → (min_cos, min_euc, qt, rd) after dedup.
    sys.intern() is used on all repeated string values to reduce object count.

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
    print("[build_moat_db] rank mode      : true-global (no sentinel)")

    if not parquet_path.exists():
        raise FileNotFoundError(f"Parquet not found: {parquet_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    # ── per-partition accumulation with min-dedup ──────────────────────────────
    # Partition key: (q_upper, effect_str, ref_type_str)
    #   effect_str = 'opposite' if direction == 'Antipodal' else 'similar'
    #
    # partitions[key][ref] = (min_cosine, min_euclidean, query_type, ref_dose)
    #   min_cosine and min_euclidean tracked independently (faithful to Loka MIN agg).
    #   ref_type comes from the partition key, not stored per row.
    #
    # sys.intern() is used on all small/repeated strings for memory efficiency.
    partitions: dict[tuple[str, str, str], dict[str, tuple]] = {}
    n_rows_seen     = 0
    n_self_excluded = 0

    # Intern the two constant effect strings up front
    _similar  = sys.intern("similar")
    _opposite = sys.intern("opposite")

    print("[build_moat_db] streaming parquet and accumulating per-partition ...")
    dataset = ds.dataset(str(parquet_path), format="parquet")
    columns = list(_COL_MAP.keys())

    batch_num = 0
    for batch in dataset.to_batches(columns=columns, batch_size=65_536):
        batch_num += 1
        if batch_num % BATCH_LOG == 0:
            total_refs = sum(len(v) for v in partitions.values())
            print(
                "  batch %d  rows_seen=%d  partitions=%d  unique_refs=%d"
                % (batch_num, n_rows_seen, len(partitions), total_refs)
            )

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
            q_upper = sys.intern(str(q_names[i]).upper()) if q_names[i] is not None else ""
            ref_val = str(r_names[i]) if r_names[i] is not None else ""

            if ref_val.upper() == q_upper:
                n_self_excluded += 1
                continue

            direction     = str(q_dirs[i]) if q_dirs[i] is not None else "Original"
            cosine_val    = float(cosines[i]) if cosines[i] is not None else 0.0
            euclidean_val = float(euclids[i]) if euclids[i] is not None else 0.0
            ref_str       = sys.intern(ref_val)
            ref_type_str  = sys.intern(str(r_types[i] or ""))
            qt            = sys.intern(str(q_types[i] or ""))
            rd            = sys.intern(str(r_doses[i] or ""))
            effect_str    = _opposite if direction == "Antipodal" else _similar
            part_key      = (q_upper, effect_str, ref_type_str)

            if part_key not in partitions:
                partitions[part_key] = {}
            ref_dict = partitions[part_key]

            existing = ref_dict.get(ref_str)
            if existing is None:
                ref_dict[ref_str] = (cosine_val, euclidean_val, qt, rd)
            else:
                # Multi-dose dedup: keep MIN(cosine) and MIN(euclidean) independently
                # (faithful to Loka global_ranking.py MIN aggregation approach)
                prev_cos, prev_euc, _, _ = existing
                ref_dict[ref_str] = (
                    min(cosine_val, prev_cos),
                    min(euclidean_val, prev_euc),
                    qt, rd,  # keep query_type and dose from first occurrence
                )

    all_part_keys = sorted(partitions)
    n_queries     = len({k[0] for k in all_part_keys})
    total_unique  = sum(len(v) for v in partitions.values())
    print(
        "[build_moat_db] done streaming: %d rows, %d self-excluded, %d queries, "
        "%d unique partition-ref entries after dedup"
        % (n_rows_seen, n_self_excluded, n_queries, total_unique)
    )

    # ── compute true global ranks and filter union per partition ───────────────
    print("[build_moat_db] computing true global ranks and writing SQLite ...")

    records: list[tuple] = []
    for part_key in all_part_keys:
        q_upper, effect_str, ref_type_str = part_key
        ref_dict = partitions[part_key]  # {ref: (min_cos, min_euc, qt, rd)}

        # TRUE global rank_cosine: sort ALL refs by (min_cos, min_euc, ref)
        items = list(ref_dict.items())
        cos_sorted = sorted(items, key=lambda x: (x[1][0], x[1][1], x[0]))
        cos_rank_map: dict[str, int] = {ref: i + 1 for i, (ref, _) in enumerate(cos_sorted)}

        # TRUE global rank_euclidean: sort ALL refs by (min_euc, min_cos, ref)
        euc_sorted = sorted(items, key=lambda x: (x[1][1], x[1][0], x[0]))
        euc_rank_map: dict[str, int] = {ref: i + 1 for i, (ref, _) in enumerate(euc_sorted)}

        # Filter: keep rank_cosine <= K OR rank_euclidean <= K
        recs: list[tuple] = []
        for ref, (cosv, eucv, qt, rd) in ref_dict.items():
            rank_cosine    = cos_rank_map[ref]    # true global rank, no sentinel
            rank_euclidean = euc_rank_map[ref]    # true global rank, no sentinel
            if rank_cosine > K and rank_euclidean > K:
                continue
            union_rank = rank_cosine + rank_euclidean
            recs.append((
                union_rank, ref,              # sort keys (dropped before storing)
                q_upper, qt, ref, ref_type_str, rd, effect_str,
                rank_cosine, rank_euclidean, union_rank, cosv, eucv,
            ))

        recs.sort(key=lambda r: (r[0], r[1]))  # union_rank ASC, ref ASC tiebreak
        for rec in recs:
            records.append(rec[2:])            # strip the two sort-key prefix values

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
            ("rank_mode", "true-global"),
            ("n_queries", str(n_queries)),
            ("n_rows",    str(len(records))),
        ]
        con.executemany("INSERT INTO moat_meta VALUES (?,?)", meta_rows)
        con.commit()
    finally:
        con.close()

    print(
        "[build_moat_db] wrote %d neighbor rows (%d queries x2 effects x ref_types) → %s"
        % (len(records), n_queries, db_path)
    )

    # ── sanity: print top-10 opposite genes for TSC2 (MTOR gene-rescue check) ──
    _print_sanity(str(db_path), "TSC2")


def _print_sanity(db_path: str, query: str) -> None:
    """Print top-5 similar and opposite for the given query as a sanity check.

    Ordered by union_rank (dual-rank metric). Also prints top-10 opposite GENE
    results for the TSC2 gene-rescue sanity check (MTOR TRUE rank verification).
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
                f"  union={row['union_rank']:3d} (cos_r={row['rank_cosine']:3d}, euc_r={row['rank_euclidean']:3d}). "
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
                f"  union={row['union_rank']:3d} (cos_r={row['rank_cosine']:3d}, euc_r={row['rank_euclidean']:3d}). "
                f"{row['ref']:<30s}  cosine={row['cosine']:.4f}  type={row['ref_type']}"
            )
        print(f"\n── Sanity: {query} opposite GENES top-10 (rescue / MTOR check) ──")
        for row in con.execute(
            "SELECT rank_cosine, rank_euclidean, union_rank, ref, ref_type, cosine "
            "FROM neighbors WHERE query=? AND effect='opposite' AND ref_type='gene' "
            "ORDER BY union_rank LIMIT 10",
            (query.upper(),),
        ):
            print(
                f"  union={row['union_rank']:3d} (cos_r={row['rank_cosine']:3d}, euc_r={row['rank_euclidean']:3d}). "
                f"{row['ref']:<30s}  cosine={row['cosine']:.4f}"
            )
        con.close()
    except Exception as exc:
        print(f"[sanity] error: {exc}")


if __name__ == "__main__":
    main()
