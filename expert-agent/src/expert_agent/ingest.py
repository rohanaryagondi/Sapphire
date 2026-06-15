"""Ingestion: load the sample corpus, parse front-matter, chunk, attach metadata.

Real ingestion would fan out across blogs/RSS, podcast/talk transcription, and
on-record social posts. Here we load local `.md` files with a YAML front-matter
header. Podcast transcription is stubbed with a clear TODO so the data flow is
visible without requiring any audio/ASR dependency.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Iterable, List, Optional

from .sources import Chunk, CredibilityTier, Document, Source

# --- Front-matter parsing ----------------------------------------------------
# We avoid a hard YAML dependency for parsing (PyYAML is optional). The sample
# front-matter is simple `key: value` pairs, so a tiny parser keeps the scaffold
# dependency-light and offline-friendly.

_FM_DELIM = re.compile(r"^---\s*$", re.MULTILINE)


def _parse_front_matter(raw: str) -> tuple[dict, str]:
    """Split a `---`-delimited front-matter header from the body."""
    parts = _FM_DELIM.split(raw, maxsplit=2)
    if len(parts) >= 3 and parts[0].strip() == "":
        meta_block, body = parts[1], parts[2]
    else:
        return {}, raw

    meta: dict = {}
    for line in meta_block.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        val = val.strip().strip('"').strip("'")
        meta[key.strip()] = val
    return meta, body.lstrip("\n")


def _parse_date(value: Optional[str]) -> Optional[_dt.date]:
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(value)
    except ValueError:
        return None


# --- Document loading --------------------------------------------------------

def load_corpus(corpus_dir: str | Path) -> List[Document]:
    """Load every `.md` file in `corpus_dir` into a Document."""
    corpus_dir = Path(corpus_dir)
    docs: List[Document] = []
    for path in sorted(corpus_dir.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta, body = _parse_front_matter(raw)

        tier = CredibilityTier(
            meta.get("credibility_tier", CredibilityTier.TIER_3_ANONYMOUS_UNVERIFIED.value)
        )
        on_record = str(meta.get("on_record", "true")).lower() in ("true", "1", "yes")

        source = Source(
            source_id=path.stem,
            author=meta.get("author", "unknown"),
            author_role=meta.get("author_role", ""),
            venue=meta.get("venue", "unknown"),
            url=meta.get("url", ""),
            credibility_tier=tier,
            on_record=on_record,
            license_note=meta.get("license_note", ""),
        )

        # Podcasts/talks would require ASR before they reach this point.
        if source.needs_transcription:
            body = _transcribe_if_needed(path, body, source)

        docs.append(
            Document(
                source=source,
                title=meta.get("title", path.stem),
                text=body,
                published=_parse_date(meta.get("date")),
            )
        )
    return docs


def _transcribe_if_needed(path: Path, body: str, source: Source) -> str:
    """STUB: podcast/talk transcription.

    TODO(prod): replace with a real ASR step. The intended production flow is:
        1. Resolve the audio URL from the source registry.
        2. Run transcription (e.g. local faster-whisper / whisper.cpp, or a
           hosted ASR API) to produce a timestamped transcript.
        3. Optionally diarize so we can attribute quotes to the right speaker.
        4. Cache the transcript keyed by source_id so we transcribe once.
    For the offline scaffold, the sample `.md` already contains a hand-written
    transcript excerpt, so we simply return it unchanged.
    """
    return body


# --- Chunking ----------------------------------------------------------------

def chunk_documents(
    docs: Iterable[Document],
    target_words: int = 90,
    overlap_words: int = 20,
) -> List[Chunk]:
    """Split documents into overlapping word-window chunks with full metadata.

    Word-window chunking is intentionally simple and deterministic. Production
    would prefer semantic/paragraph-aware chunking, but the metadata contract
    (author, date, venue, tier, on_record) is the part that actually matters
    for grounded citation, and that is fully preserved here.
    """
    chunks: List[Chunk] = []
    for doc in docs:
        # Drop the markdown H1 title line from the body to reduce boilerplate.
        body = re.sub(r"^#\s.*$", "", doc.text, count=1, flags=re.MULTILINE).strip()
        words = body.split()
        if not words:
            continue

        step = max(1, target_words - overlap_words)
        idx = 0
        for start in range(0, len(words), step):
            window = words[start : start + target_words]
            if not window:
                continue
            text = " ".join(window)
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.source.source_id}#{idx}",
                    text=text,
                    source_id=doc.source.source_id,
                    author=doc.source.author,
                    author_role=doc.source.author_role,
                    venue=doc.source.venue,
                    url=doc.source.url,
                    title=doc.title,
                    published=doc.published,
                    credibility_tier=doc.source.credibility_tier,
                    on_record=doc.source.on_record,
                    credibility_weight=doc.source.credibility_weight,
                )
            )
            idx += 1
            if start + target_words >= len(words):
                break
    return chunks
