# Proposal: Expert Agent (CAP-15) for Quiver Bioscience

**Capability:** CAP-15 — Expert judgment / strategic reasoning
**Status:** Proposal + runnable scaffold (see [`README.md`](./README.md))
**Date:** 2026-06-15
**Author:** Rohan Gondi (rohan.gondi@quiverbioscience.com)

---

## 1. Vision, and the stock-bot analog

### The idea (James, 2026-06-11)

> "There is a company of 10 people, [pharma] experts with 20 years experience in
> CNS, regulatory experience about how to gauge the FDA, what's the right safety
> studies, how you design clinical trials, and you have to pay them like $50,000
> for their expertise. I believe very strongly that we could find public blog
> posts, tweets, podcasts of those types of experts where they've given all of
> their knowledge for free. And we can build an agent who can do just as good as
> Sally from Pfizer with 25 years experience, because she was posting all about
> her lessons and her knowledge and her wisdom on Twitter for the past 10 years."

Rohan's analog: financial-market sentiment/prediction bots that do semantic
analysis over public information — **"change stocks to biology."** James:
**"let's not reinvent the wheel."**

### What transfers from the stock-bot world

The financial-sentiment literature has already solved most of the *plumbing* we
need, and we should borrow it directly:

- **Many noisy public sources, fused into a directional view.** These pipelines
  ingest news, filings, Reddit, and Twitter, then produce a weighted synthesis.
  That is exactly our shape — only the documents are regulatory/clinical, not
  market, content.
- **Dynamic source-credibility weighting.** Production sentiment systems assign
  each source a *normalized reliability weight* and validate it against ground
  truth (market feedback). We adopt per-source credibility tiers (§3).
- **A recency modality.** These systems explicitly separate "timely" vs.
  "trending" opinions and decay older signal. CNS regulatory expectations drift
  (e.g., evolving DRG-toxicity scrutiny for ASOs), so recency weighting matters
  here too.
- **Source diversity as a feature.** Diverse sources improve RAG robustness;
  the same holds for an expert panel.

### What does NOT transfer (and why this is the crux)

- **There is no "market feedback" oracle.** A stock bot is graded continuously
  by price movement. We have no equivalent automatic ground truth, so our
  reliability has to come from *citation + held-out evaluation*, not from a
  self-correcting feedback loop. This is the single biggest difference and it
  drives the whole reliability plan in §5.
- **Persona ≠ accuracy.** James's framing — "do just as good as Sally from
  Pfizer" — is the right *aspiration* but the wrong *mechanism* if read as
  "make the model pretend to be Sally." Recent controlled studies (2024–2026)
  find that assigning an expert persona to an LLM has **near-zero or negative
  effect on factual accuracy**, even when the persona matches the task domain;
  several find it *damages* accuracy on knowledge benchmarks. Persona helps
  *tone and framing*, not correctness.
  - **Design consequence:** we do **not** rely on "pretend you are Dr. X." Every
    substantive claim is grounded in *retrieved, cited, public source material*
    (RAG / GraphRAG). The "expert voice" is at most archetype/role-level framing
    layered on top of cited facts — never a substitute for them.
- **Stakes and liability are higher.** A wrong stock call loses money; wrong
  regulatory guidance can sink an IND or harm trial subjects. That forces
  calibrated **abstention** and a hard **human-in-the-loop** posture.

### Comparable shipped products (we are not first; that's good)

- **AlphaSense Generative Search** — natural-language Q&A over a library of
  expert-call transcripts and filings, with **every answer linking back to the
  exact source snippet**. This is the citation-grounded pattern we mirror.
- **Cortellis Regulatory AI Assistant (Clarivate, launched Dec 2025)** — agentic
  AI that returns **precise, cited answers** to regulatory questions over a
  curated regulatory corpus.

**Honest positioning:** *none* of these claim to faithfully emulate a *named
individual*. They synthesize and cite a *corpus*. We will make the same honest
claim. We are building a cited-synthesis engine over public expert content — not
a digital clone of Sally.

---

## 2. Architecture

```
 ┌─────────────────┐
 │ Source registry │  public sources only; per-source credibility tier + on-record flag
 └────────┬────────┘
          ▼
 ┌─────────────────────────────────────────────┐
 │ Ingestion                                    │
 │  • blogs / RSS (HTML + feed parse)           │
 │  • podcasts / talks → ASR transcription      │  (Whisper-class; STUBBED in scaffold)
 │  • on-record social posts                    │
 └────────┬────────────────────────────────────┘
          ▼
 ┌─────────────────────────────────────────────┐
 │ Chunking + metadata                          │
 │  author · date · venue · credibility tier ·  │
 │  on-record flag · source URL                 │
 └────────┬────────────────────────────────────┘
          ▼
 ┌─────────────────────────────────────────────┐
 │ Stores                                       │
 │  • vector index (embeddings)                 │
 │  • graph store (entities/relations, GraphRAG)│  for multi-hop questions
 └────────┬────────────────────────────────────┘
          ▼
 ┌─────────────────────────────────────────────┐
 │ Credibility + recency weighted retrieval     │
 │  final = sim^a · credibility^b · recency^c   │
 └────────┬────────────────────────────────────┘
          ▼
 ┌─────────────────────────────────────────────┐
 │ Grounded, cited synthesis                    │
 │  answer ONLY from retrieved sources;         │
 │  inline citations; surface disagreement      │
 └────────┬────────────────────────────────────┘
          ▼
 ┌─────────────────────────────────────────────┐
 │ Calibrated uncertainty / abstention          │
 │  thin or weak evidence → abstain + escalate  │
 └─────────────────────────────────────────────┘
```

**Framework choices (confirmed against 2024–2026 practice).** No single winner;
pick per-layer:
- **LlamaIndex** for ingestion/indexing/retrieval (benchmarks show faster, more
  RAG-focused retrieval; strong document-pipeline ergonomics).
- **LangChain / LangGraph** for agentic orchestration (the expert-panel debate
  loop, tool calls, multi-step flows).
- **Microsoft GraphRAG** for the graph layer that answers multi-hop / "connect
  these themes" questions that naive vector RAG handles poorly. LlamaIndex,
  LangChain, and Semantic Kernel all interoperate with GraphRAG, so this is not
  a lock-in.
- **Whisper-class ASR** (e.g. local faster-whisper / whisper.cpp) for podcast and
  talk transcription — the standard 2025–2026 audio-RAG ingest path, runnable
  offline with no per-call API cost.

The scaffold implements the registry, ingestion (markdown), chunking+metadata,
a deterministic TF-IDF *stand-in* for the vector index, the weighted retrieval,
the grounded extractive synthesis, and abstention. The vector DB, graph store,
real ASR, and LLM synthesis are documented optional upgrades.

---

## 3. The expert-panel model

Rather than one blended voice, we model **per-expert corpora** and let them
**debate**:

1. **Per-expert corpora.** Each registered expert is a namespace: all of *their*
   public content is tagged to them, with their credibility tier and role.
2. **Panel retrieval.** A question retrieves the top chunks *per expert*, not
   just globally, so a minority but highly-credentialed view is not buried by a
   prolific low-tier poster.
3. **Multi-expert debate → surface disagreement.** The synthesis step explicitly
   reports *where experts disagree* instead of averaging it away. A LangGraph
   debate loop (v1) can have each expert-conditioned retrieval argue its position
   and a neutral aggregator report the spread. The scaffold already implements a
   lightweight version: it flags when retrieved views span multiple experts and
   when any excerpt is off-record/speculative.
4. **Archetype, not clone.** A "panelist" is *the role* ("former FDA neurology
   reviewer"), grounded in that person's *cited public statements* — never a
   claim to *be* that named living individual (see §6).

---

## 4. Source-credibility model

Borrowed from financial-sentiment source weighting; three coarse tiers, tunable
in `config.example.yaml`:

| Tier | Example | Default weight |
|---|---|---|
| `tier_1_named_credentialed` | named ex-FDA reviewer, credentialed MD/PhD, on record | 1.0 |
| `tier_2_named_practitioner` | named industry practitioner, identified author | 0.7 |
| `tier_3_anonymous_unverified` | anonymous / unverified / pseudonymous | 0.4 |

Plus an **on-record vs. speculative** axis: off-record material (a hot take on a
podcast, an explicitly hedged "don't quote me") is multiplied by an additional
discount (0.6 in the scaffold). Final retrieval score:

```
final = similarity^a · credibility_weight^b · recency_weight^c
recency_weight = 0.5 ^ (age_days / halflife)     # halflife ≈ 18 months
```

This is exactly what lets the scaffold rank a tier-1 ex-FDA blog above a *more
recent* anonymous podcast "hot take," while still surfacing the latter, flagged.

---

## 5. Reliability & validity plan (addresses Rohan's data-reliability and cost concerns)

This is the part the stock-bot analogy *cannot* hand us for free, because we have
no market-feedback oracle. Four mechanisms:

1. **Hard citation requirement.** Every claim must trace to a retrieved public
   source with author/date/venue/URL. Ungrounded sentences are dropped. (The
   offline scaffold makes this trivially auditable by being *extractive* — it
   only ever emits cited source text.)
2. **Credibility scoring + recency weighting.** §4. Reliability is *built into
   ranking*, not bolted on after.
3. **Held-out expert-statement evaluation.** Take public expert statements the
   system has **not** ingested (e.g., a later post, a conference Q&A) and check
   whether the agent's grounded answer is *consistent* with what that expert
   actually said. This is our closest analog to the stock bot's backtest:
   - Metrics: citation precision (do cited snippets support the claim?),
     answer-vs-held-out agreement, abstention correctness (did it abstain when it
     should have?), and disagreement recall (did it surface real splits?).
4. **Calibrated abstention.** When the best evidence is thin or weak, the agent
   **abstains and escalates to a human**, rather than emitting a confident
   guess. Thresholds are conservative and tunable.

**On Rohan's data-reliability concern:** garbage public content is the central
risk. The credibility tiers, on-record discount, recency decay, and held-out
eval are the controls. We should also **manually curate the initial source
registry** (a small, vetted set of high-tier experts) before any broad crawl —
quality of registry beats quantity of crawl.

**On Rohan's ingestion-cost concern:**
- Transcription is the main cost driver. Use **local Whisper-class ASR** (no
  per-minute API fee) and **transcribe-once / cache** keyed by source ID.
- Embeddings: batch and cache; local embedding models avoid per-token fees.
- Re-ingest on a cadence (e.g., RSS deltas) rather than re-crawling everything.
- The offline scaffold deliberately costs **\$0** to run — proof the core loop
  needs no paid API.

---

## 6. Legal & ethical guardrails

- **Public content only.** We ingest only publicly available material. We never
  ingest or transmit Quiver proprietary functional/EP/CRISPR data through this
  agent. (Enforced as a scope rule and a registry-review step.)
- **ToS / copyright.** Respect each platform's terms of service and robots
  directives; store *short excerpts + links back to the source* rather than
  wholesale copies, mirroring how AlphaSense/Cortellis cite snippets. Keep a
  per-source license note (the registry has a field for it).
- **Right of publicity / no impersonation.** **Do not impersonate a named living
  person.** We emulate an *archetype/role* ("former FDA neurology reviewer") and
  **attribute every quoted claim to its cited source**. We do not present
  generated text *as if authored by* a named individual, and we do not market the
  product as "Sally from Pfizer in a box."
- **Honest fidelity claims.** No comparable product claims faithful emulation of
  an individual, and neither will we. Public marketing and internal use must
  describe this as *cited synthesis over public expert content* with documented
  limits.
- **Not regulatory advice.** Output is decision *support* for Quiver's internal
  strategy, gated by a human expert — not a regulatory filing or legal advice.

---

## 7. Phased build plan

**Phase 0 — Scaffold (done; this repo).** Offline, no keys: registry +
credibility tiers, markdown ingestion, chunking+metadata, TF-IDF retrieval with
credibility/recency weighting, extractive cited synthesis, abstention,
disagreement flagging. Proves the loop end-to-end at \$0.

**Phase 1 — MVP (4–6 wks).**
- Real embeddings + a vector DB (e.g. Chroma/Qdrant) replacing TF-IDF.
- LlamaIndex ingestion for blogs/RSS + HTML.
- Whisper ASR ingest path for podcasts/talks (replaces the stub).
- LLM-backed abstractive synthesis under a strict *"answer only from cited
  sources"* contract; keep the extractive path as a fallback/audit mode.
- Curated registry of ~10–20 vetted high-tier CNS regulatory/clinical experts.
- First held-out eval set.

**Phase 2 — v1 (next quarter).**
- GraphRAG graph store for multi-hop / thematic questions.
- LangGraph multi-expert **debate** loop that surfaces disagreement.
- Calibrated confidence (tuned thresholds against the eval set).
- Source-freshness jobs (RSS deltas, scheduled re-ingest).
- Reviewer UI: answer + citations + confidence + "escalate to human" action.

---

## 8. Where this plugs into Sapphire

CAP-15 has **no off-the-shelf model**; this agent fills it. Quiver's core is CNS
drug discovery (functional genomics / EP / CRISPR target prediction). The expert
agent wraps **regulatory / clinical-trial-design / strategic-judgment context**
around those target predictions:

- **Provides CAP-15 context** to the rest of the Sapphire capability map: when a
  target prediction surfaces, the expert agent supplies cited public-expert
  perspective on the *development path* (safety-study expectations, FIH design,
  likely FDA scrutiny points).
- **Safety/regulatory gating.** It acts as an advisory gate around target
  predictions — e.g., flagging that a given modality (ASO) carries known
  class-level safety scrutiny (DRG toxicity, NHP chronic tox) that should shape
  prioritization — always cited, always human-reviewed.
- **Strict data boundary.** It consumes Quiver's *prediction outputs* as the
  question context but sends **no proprietary data** outward; it reasons only
  over public expert content.

---

## Appendix — Sources consulted (2024–2026 practice check)

- Microsoft GraphRAG vs. naive RAG; LangChain vs. LlamaIndex 2025 RAG comparisons
  (retrieval-speed and use-case fit).
- Persona-effect studies: "Expert Personas Improve LLM Alignment but Damage
  Accuracy" (arXiv 2603.18507); "Playing Pretend: Expert Personas Don't Improve
  Factual Accuracy" (SSRN 5879722); "Quantifying the Persona Effect in LLM
  Simulations."
- Financial-sentiment source-weighting / recency-modality work (dynamic source
  reliability weights; timely-vs-trending opinion fusion; DeepTrust reliable
  financial knowledge retrieval).
- AlphaSense Generative Search over expert-call transcripts (snippet-linked
  citations); Clarivate Cortellis Regulatory AI Assistant (cited regulatory
  answers, Dec 2025).
- Whisper-based audio-RAG ingestion patterns (local transcription → chunk →
  index).
