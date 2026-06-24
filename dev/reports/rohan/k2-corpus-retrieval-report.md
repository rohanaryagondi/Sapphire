# Task K2 — corpus runtime retrieval (corpus-first → search-the-gap) — report

**Branch:** `rohan/k2-corpus-retrieval`
**Built-By:** rohan
**Tier:** Feature

## Goal
Make Bucket-1 agents actually **read their knowledge corpus** at run time, so the stable ~70% of
each agent's domain is answered locally and only the gap goes to live web/EMET. Today the corpora
(`sapphire-orchestrator/corpus/<agent>/`) are inert; FDA-memory ships a 45-card `index.jsonl`.

## What shipped

### 1. Stdlib corpus reader — `corpus/reader.py`
`read_corpus(agent_id, query, entities=None, *, top_n=5, base_dir=None) -> list[dict]`:
- Loads `corpus/<agent_id>/index.jsonl` (one claim-card per line); skips blank/malformed lines
  (never fabricates a hit from a bad line).
- Builds query terms from the query text (lowercased content tokens ≥3 chars, minus stopwords) **+**
  entity terms (`genes` / `diseases` / `drugs`).
- Scores each card by term overlap against its lens fields (`claim`, `drug`, `indication`,
  `decision`, `reason`, `precedent_implication`, `quote`, trial fields, …); keeps overlap > 0,
  ranks by overlap desc (stable by original order), caps to `top_n`.
- `has_corpus(agent_id)` helper. Returns `[]` for **no corpus dir** (agents without a corpus are
  unchanged) and for **no match / empty query** (honest empty). Stdlib only (`json`, `re`).

### 2. Wired into the Bucket-1 dispatch — `live_engine.py`
Inside the `for agent_id in _BUCKET1_AGENTS` loop, for any agent with a `corpus/<id>/` dir:
- Fetch matching cards and **hand them to the agent** as `corpus_hits` in its inputs (so its live
  call targets the gap).
- After dispatch, surface each card as a **corpus-sourced dossier fact** via `_corpus_card_to_fact`:
  carries the card's own `source` / `tier` / `url`, stamps `provenance="corpus"` + `from_corpus=True`
  + `field=<agent_id>`. Corpus facts land **independent of whether the live agent ran** — the point
  of corpus-first: the stable knowledge is there even when the live backend is down.
- **Traced:** a `corpus_retrieval` event (`agent_id`, `n_cards`, fact previews) is appended to the
  harness trace.
- **Generic:** no per-agent code — any agent that grows a `corpus/<id>/` dir benefits automatically.

### 3. Provenance + veto integrity
- Added the `corpus` label to `contracts/provenance.py` (an allowed label, documented as a **T2
  lead, never a dispositive veto**).
- **Veto rule intact:** `_corpus_card_to_fact` deliberately sets **no `flag`**, so a corpus card —
  even a `decision=CRL`/`approval`/T1 card — never populates the VETO flag list. A dispositive veto
  still requires its T1 primary (per the FDA-memory skill doc). Asserted by a dedicated test.

## Gate evidence

- **Gate 1 — full suite:** `bash dev/run-tests.sh` → **368 GREEN** (contracts 29 · harness 68 ·
  emet 18 · memory 14 · selfimprove 20 · moat 68 · **corpus 8** · tests 143). +12 new
  (8 reader unit + 4 run_live integration). Added `corpus` to the Gate-1 runner module loop so the
  reader tests run in Gate 1 + the pre-push hook. No warnings (fixed an unclosed-file ResourceWarning).
- **Gate 3 — provenance/secrets:** no secrets/binaries. New provenance label `corpus` is in the
  allowed set (`is_valid_provenance("corpus")` → True). Corpus cards are public FDA precedent
  (public-identifiers-only intact).
- **Gate 4 — stdlib runtime:** grep of `reader.py` / `live_engine.py` for
  pandas/numpy/sklearn/scipy/pyarrow/requests/torch/joblib → **none**.
- **Gate 5 — functional verification (RAN it):**
  - Through `run_live` (offline mock ctx, real FDA corpus): the aducanumab/Alzheimer's query yields
    **5 corpus-sourced dossier facts** (`provenance=corpus`, `from_corpus=True`, own source/tier/url),
    VETO flags empty, and a `corpus_retrieval` trace event with `n_cards=5`.
  - Through the **real `/api/run` HTTP front door** (K1's boundary, `via=engine-live`): same query →
    5 corpus facts in the dossier; VETO empty.
  - **Honest-empty:** a non-precedent query (`Is SCN2A a viable ion channel target?`) → **0 corpus
    facts** (no fabrication).
  - Adversarial unit tests: malformed JSON line skipped (not fabricated), empty/stopword-only query →
    `[]`, unknown agent → `[]`, `top_n` cap respected.

Server runtime artifacts produced during Gate-5 were reverted; offline tests use temp
`SAPPHIRE_ENGAGEMENTS_DIR`/`SAPPHIRE_MEMORY_DIR`.

## Notes / first-cut scope (per brief)
- "Surfacing corpus facts into the dossier + handing the agent the hits is the 80%" — done. The live
  agent still runs for the uncovered part (it receives `corpus_hits` as context).
- No dedup yet between a corpus card and an identical live-agent fact (acceptable for the first cut;
  corpus facts are clearly marked `from_corpus`).

## Files
- `sapphire-orchestrator/corpus/reader.py` (new)
- `sapphire-orchestrator/corpus/__init__.py`, `corpus/tests/__init__.py`, `corpus/tests/test_reader.py` (new)
- `sapphire-orchestrator/tests/test_corpus_retrieval.py` (new)
- `sapphire-orchestrator/live_engine.py` (modified)
- `sapphire-orchestrator/contracts/provenance.py` (modified — `corpus` label)
- `dev/run-tests.sh` (modified — `corpus` in the Gate-1 module loop)
