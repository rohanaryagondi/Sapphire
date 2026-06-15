"""End-to-end pipeline wiring: corpus -> chunks -> index -> retrieve -> answer."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .ingest import chunk_documents, load_corpus
from .retrieve import RetrievalConfig, retrieve
from .store import build_index
from .synthesize import Answer, synthesize


def answer_question(
    question: str,
    corpus_dir: str | Path,
    config: Optional[RetrievalConfig] = None,
) -> Answer:
    docs = load_corpus(corpus_dir)
    chunks = chunk_documents(docs)
    index = build_index(chunks)
    ranked = retrieve(index, question, config=config)
    return synthesize(question, ranked)
