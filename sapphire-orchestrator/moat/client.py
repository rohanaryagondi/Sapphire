"""
moat/client.py — stdlib SQLite moat client (Task 2).

Read-only access to the Quiver internal moat SQLite database.
No third-party dependencies: sqlite3, os, pathlib only.
"""
import os
import sqlite3
from pathlib import Path

PROVENANCE = "moat-real"

# Default DB path relative to the repo root (two levels up from sapphire-orchestrator/)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_DB = _REPO_ROOT / "RohanOnly" / "moat" / "moat.sqlite"


class MoatClient:
    """
    Read-only client over the Quiver moat SQLite database.

    Resolution order for db_path:
      1. Constructor arg `db_path`
      2. Env var SAPPHIRE_MOAT_DB
      3. Default: <repo>/RohanOnly/moat/moat.sqlite
    """

    def __init__(self, db_path: str | None = None):
        if db_path is not None:
            self.db_path = str(db_path)
        elif os.environ.get("SAPPHIRE_MOAT_DB"):
            self.db_path = os.environ["SAPPHIRE_MOAT_DB"]
        else:
            self.db_path = str(_DEFAULT_DB)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self):
        """Return a read-only connection, or None if the file is absent."""
        p = Path(self.db_path)
        if not p.exists():
            return None
        try:
            uri = f"file:{p.as_posix()}?mode=ro"
            con = sqlite3.connect(uri, uri=True)
            con.row_factory = sqlite3.Row
            return con
        except Exception:
            return None

    def _has_neighbors_table(self, con) -> bool:
        try:
            cur = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='neighbors'"
            )
            return cur.fetchone() is not None
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def available(self) -> bool:
        """True iff the DB file exists and contains the 'neighbors' table."""
        con = self._connect()
        if con is None:
            return False
        try:
            return self._has_neighbors_table(con)
        except Exception:
            return False
        finally:
            try:
                con.close()
            except Exception:
                pass

    def neighbors(
        self,
        perturbation: str,
        effect: str = "similar",
        ref_type: str | None = None,
        k: int = 10,
    ) -> list[dict]:
        """
        Return up to k neighbor rows for `perturbation` (case-insensitive).

        Args:
            perturbation: gene symbol or compound name (matched UPPERCASE).
            effect: "similar" | "opposite".
            ref_type: optional filter — "gene" | "compound".
            k: max rows to return.

        Returns:
            List of dicts with keys:
                query, ref, ref_type, ref_dose, effect, rank,
                cosine, euclidean, provenance.
            Returns [] if unavailable, no match, or any error — never raises.
        """
        try:
            con = self._connect()
            if con is None:
                return []
            if not self._has_neighbors_table(con):
                con.close()
                return []

            query_upper = perturbation.upper()

            if ref_type is not None:
                sql = """
                    SELECT query, ref, ref_type, ref_dose, effect, rank, cosine, euclidean
                    FROM neighbors
                    WHERE query = ? AND effect = ? AND ref_type = ?
                    ORDER BY rank
                    LIMIT ?
                """
                params = (query_upper, effect, ref_type, k)
            else:
                sql = """
                    SELECT query, ref, ref_type, ref_dose, effect, rank, cosine, euclidean
                    FROM neighbors
                    WHERE query = ? AND effect = ?
                    ORDER BY rank
                    LIMIT ?
                """
                params = (query_upper, effect, k)

            cur = con.execute(sql, params)
            rows = cur.fetchall()
            con.close()

            result = []
            for row in rows:
                result.append({
                    "query":     row["query"],
                    "ref":       row["ref"],
                    "ref_type":  row["ref_type"],
                    "ref_dose":  row["ref_dose"],
                    "effect":    row["effect"],
                    "rank":      row["rank"],
                    "cosine":    row["cosine"],
                    "euclidean": row["euclidean"],
                    "provenance": PROVENANCE,
                })
            return result

        except Exception:
            return []

    def health(self) -> dict:
        """
        Return a health dict:
            {available: bool, db_path: str, n_rows: int, meta: dict}

        n_rows counts all rows in 'neighbors'; meta is from moat_meta (key→value).
        Safe to call even when the DB is absent.
        """
        avail = self.available()
        n_rows = 0
        meta: dict = {}

        if avail:
            try:
                con = self._connect()
                if con is not None:
                    try:
                        cur = con.execute("SELECT COUNT(*) FROM neighbors")
                        row = cur.fetchone()
                        n_rows = row[0] if row else 0
                    except Exception:
                        pass
                    try:
                        cur = con.execute("SELECT key, value FROM moat_meta")
                        meta = {r[0]: r[1] for r in cur.fetchall()}
                    except Exception:
                        pass
                    con.close()
            except Exception:
                pass

        return {
            "available": avail,
            "db_path":   self.db_path,
            "n_rows":    n_rows,
            "meta":      meta,
        }
