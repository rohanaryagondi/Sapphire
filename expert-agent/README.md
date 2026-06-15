# Expert Agent (CAP-15) — Runnable Scaffold

A minimal, **offline-runnable** scaffold for Quiver Bioscience's "expert agent":
a citation-grounded synthesis tool that answers regulatory / clinical-trial-design /
strategic-judgment questions using **public expert content only** (blogs, RSS,
podcast/talk transcripts, on-record posts).

This is the engineering companion to [`PROPOSAL.md`](./PROPOSAL.md). Read the
proposal for the vision, architecture rationale, reliability/validity plan, and
the legal/ethical guardrails.

> **Scope guardrail:** This agent works on PUBLIC expert material. It must never
> ingest or transmit Quiver's proprietary functional / EP / CRISPR data.

---

## What runs today vs. what is stubbed

| Component | Status in this scaffold |
|---|---|
| Source registry + credibility tiers (`sources.py`) | **Real** (dataclasses + weighting logic) |
| Markdown corpus ingestion + chunking + metadata (`ingest.py`) | **Real** |
| Podcast/talk transcription (ASR) | **STUB** — clearly marked `TODO` in `ingest.py`; sample uses a hand-written transcript |
| Embedding index (`store.py`) | **Real but a fallback** — deterministic pure-Python TF-IDF (no ML deps, no keys) |
| Credibility + recency weighted retrieval (`retrieve.py`) | **Real** |
| Grounded, inline-cited synthesis (`synthesize.py`) | **Real, extractive** — LLM-backed abstractive synthesis is a documented optional path |
| Calibrated confidence / abstention | **Real** (conservative thresholds) |
| Multi-expert disagreement / off-record flagging | **Real** |
| Vector DB / GraphRAG / RSS / LLM synthesis | **Not included** — optional deps listed in `requirements.txt` |

The sample corpus in [`sample_corpus/`](./sample_corpus/) is **FICTIONAL** demo
content written for this scaffold. The authors are not real people.

---

## Setup

Requires **Python 3.9+**. The default offline path needs **nothing beyond the
standard library** — no `pip install`, no API keys.

```bash
# from the repository root
python expert-agent/run.py "What safety studies should precede a CNS ASO IND?"
```

If you omit the question it uses a built-in default.

Optional production dependencies (embeddings, GraphRAG, Whisper, LLM synthesis)
are listed — commented out — in [`requirements.txt`](./requirements.txt).

---

## Example output (verified)

Running the sample question returns ranked, inline-cited excerpts. The tier-1
ex-FDA blog ranks at the top; the recent anonymous podcast "hot take" is pulled
in but **flagged off-record/speculative and down-weighted**; a panel note warns
that the retrieved views span multiple experts and should not be read as
consensus. A confidence label and a full `Sources:` list are printed.

---

## How the pieces connect

```
sample_corpus/*.md
      │  load_corpus + front-matter parse        (ingest.py)
      ▼
   Documents ──► chunk_documents (metadata-rich) (ingest.py)
      │
      ▼
   Chunks  ──► build_index (TF-IDF, deterministic)(store.py)
      │
      ▼
   query + re-rank by sim^a · credibility^b · recency^c   (retrieve.py)
      │
      ▼
   synthesize → grounded, inline-cited answer + abstention (synthesize.py)
```

`pipeline.answer_question()` wires these together; `run.py` is the CLI.

---

## Known limitations (be honest with stakeholders)

- **Lexical, not semantic, fallback.** The offline TF-IDF index matches on word
  overlap. It will sometimes score an off-domain question as "relevant" because
  of incidental token overlap. Real embeddings (and a tuned abstain threshold)
  are what reliably gate off-domain queries in production. Treat the offline
  confidence label as illustrative, not calibrated.
- **No real ASR.** Podcasts are represented by a hand-written transcript.
- **Extractive synthesis.** The offline answer surfaces source snippets verbatim;
  it does not paraphrase or reason across them. That is intentional — it keeps
  the grounding guarantee trivially auditable with no model in the loop.
- **Tiny corpus.** Three documents. Retrieval quality scales with corpus breadth.

---

## Next steps toward v1

See `PROPOSAL.md` → "Phased build plan." In short: swap TF-IDF for real
embeddings + a vector DB, add the Whisper ASR ingest path, add RSS/social
ingestion, layer a graph store for multi-hop questions, and enable LLM-backed
abstractive synthesis under a strict "answer only from cited sources" contract.
