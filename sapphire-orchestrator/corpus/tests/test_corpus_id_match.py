"""Guard test: every corpus/ dir must match a live _BUCKET1_AGENTS id.

Catches the mismatch class that caused silent K2 skips for three agents
(financial-investor / kol-social-signal / reputational-institutional). This test
FAILED on pre-fix main and passes after WO-6 Phase 0 Task 1 (rename) + Task 2
(new corpora for payer / manufacturing-cmc).

Rules:
- Derives agent ids from _BUCKET1_AGENTS in live_engine (the authoritative source).
- Derives corpus dirs from disk (directories under corpus/ that contain index.jsonl).
- fda-institutional-memory is in _BUCKET1_AGENTS, so it is never a false orphan.
- Stdlib-only, offline ($0, no network).
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # corpus/tests/
_CORPUS_ROOT = _HERE.parent                      # corpus/
_PKG = _CORPUS_ROOT.parent                       # sapphire-orchestrator/

if str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from corpus.reader import has_corpus, _load_cards  # noqa: E402
from live_engine import _BUCKET1_AGENTS            # noqa: E402


class TestCorpusIdMatch(unittest.TestCase):
    """Every corpus/ dir must correspond to a live agent id; every id with a
    corpus dir must load >= 1 card.
    """

    def _disk_dirs(self) -> set[str]:
        """Names of sub-directories under corpus/ that contain index.jsonl."""
        return {
            d.name
            for d in _CORPUS_ROOT.iterdir()
            if d.is_dir() and (d / "index.jsonl").is_file()
        }

    def test_no_orphan_corpus_dirs(self):
        """Every corpus dir must map to a live _BUCKET1_AGENTS id.

        An orphan dir means has_corpus(agent_id) will never be True for it,
        silently skipping K2 for that agent.
        """
        agent_ids = set(_BUCKET1_AGENTS)
        disk_dirs = self._disk_dirs()
        orphans = disk_dirs - agent_ids
        self.assertFalse(
            orphans,
            f"corpus dirs with no matching agent id (silent K2 skip): {sorted(orphans)}\n"
            f"  Rename the dir to the short agent id (no alias needed in the reader)."
        )

    def test_all_corpus_dirs_load_at_least_one_card(self):
        """Every corpus dir identified on disk must load >= 1 card via the reader."""
        disk_dirs = self._disk_dirs()
        empty = []
        for aid in sorted(disk_dirs):
            cards = _load_cards(aid, base_dir=_CORPUS_ROOT)
            if not cards:
                empty.append(aid)
        self.assertFalse(
            empty,
            f"corpus dirs that load 0 cards (empty or all-malformed): {empty}"
        )

    def test_all_corpus_dirs_recognised_by_has_corpus(self):
        """has_corpus(id) must be True for every id that has a corpus dir."""
        disk_dirs = self._disk_dirs()
        missing = []
        for aid in sorted(disk_dirs):
            if not has_corpus(aid, base_dir=_CORPUS_ROOT):
                missing.append(aid)
        self.assertFalse(
            missing,
            f"has_corpus() returns False for these ids despite an index.jsonl: {missing}"
        )

    def test_explicit_pins_renamed_and_new_agents(self):
        """Explicit pins for the 5 agents this WO fixed or added.

        These were either silently-skipped (id mismatch) or missing entirely
        before WO-6 Phase 0. Each must now have has_corpus == True and >= 1 card.
        """
        pins = ("financial", "kol-social", "reputational", "payer", "manufacturing-cmc")
        for aid in pins:
            with self.subTest(agent=aid):
                self.assertTrue(
                    has_corpus(aid, base_dir=_CORPUS_ROOT),
                    f"has_corpus('{aid}') is False — corpus dir or index.jsonl missing"
                )
                cards = _load_cards(aid, base_dir=_CORPUS_ROOT)
                self.assertGreaterEqual(
                    len(cards), 1,
                    f"_load_cards('{aid}') returned 0 cards — index.jsonl empty or all-malformed"
                )


if __name__ == "__main__":
    unittest.main()
