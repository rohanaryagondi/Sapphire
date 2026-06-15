#!/usr/bin/env python3
"""CLI entry point for the Expert Agent scaffold (CAP-15).

Runs fully offline over the bundled sample corpus. No API keys required.

Usage:
    python expert-agent/run.py "What safety studies should precede a CNS ASO IND?"
    python expert-agent/run.py            # uses the default sample question
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `src/` importable whether run from repo root or the expert-agent dir.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "src"))

from expert_agent.pipeline import answer_question  # noqa: E402

DEFAULT_QUESTION = "What safety studies should precede a CNS ASO IND?"
CORPUS_DIR = _HERE / "sample_corpus"


def main() -> int:
    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION

    print("=" * 78)
    print("Quiver Expert Agent (CAP-15) — OFFLINE EXTRACTIVE MODE (no API keys)")
    print("Public expert content only. Sample corpus is FICTIONAL demo data.")
    print("=" * 78)
    print(f"Question: {question}\n")

    answer = answer_question(question, CORPUS_DIR)
    print(answer.body)
    print()
    print("-" * 78)
    print(f"abstained={answer.abstained} confidence={answer.confidence}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
