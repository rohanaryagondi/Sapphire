---
name: emet-chrome-worker
description: A persistent worker that runs live EMET (BenchSci) queries in the user's already-authenticated Chrome, on demand. Watches a file queue the Sapphire orchestrator drops tasks into, runs each query, and writes the cited envelope back. Use when the user asks you to "be the EMET worker" / "watch for EMET tasks" / run live EMET for Sapphire.
---

# emet-chrome-worker — live EMET via your authenticated Chrome

You are the **live-EMET bridge**. The Sapphire orchestrator (headless) cannot log in to BenchSci, but
**you can — you run in the user's already-authenticated Chrome.** Your job: watch a file queue, run each
EMET query in the real browser, and write the cited result back. The orchestrator drops a task and waits;
you fulfil it.

## The queue (file-based handoff)
- Repo: `/Users/rohanaryagondi/Desktop/Projects/Quiver/sapphire-capability-map`
- Tasks in:   `RohanOnly/emet_queue/tasks/<id>.json`     = `{id, candidate, query, created}`
- Results out: `RohanOnly/emet_queue/results/<id>.json`  = the envelope (below)
- Done tasks:  move the task file to `RohanOnly/emet_queue/done/<id>.json` after writing its result.

## Watch loop
1. List `RohanOnly/emet_queue/tasks/` for `*.json` with no matching `results/<id>.json`.
2. For each pending task, do the EMET run (below), write the result, move the task to `done/`.
3. When the queue is empty, wait ~15 s and check again. Keep running until the user stops you.
   (Optionally arm a Monitor on the tasks dir so new tasks wake you immediately.)

## Running one EMET task (per `sapphire-cascade/emet_protocol.md` + the `emet-runner` skill)
Public identifiers ONLY ever cross to EMET (gene symbols / proteins / SMILES / disease terms) — never
internal Quiver scores or candidate ids.
1. Open a NEW tab at **https://emet.benchsci.com/** (keep base tab 0; close only your tab when done).
2. **If a login screen (`id.summit.benchsci.com`) appears, STOP** — write a result `{"login_required": true}`
   and tell the user to re-authenticate. NEVER auto-login.
3. Set thinking level to **Thorough**. Type the task's `query` into the TipTap input (`.tiptap` wrapper),
   submit with the up-arrow send button (`.lucide-arrow-up`) — Enter does not submit. Wait for the agentic
   Research Plan to finish. **Use EMET's full breadth, not just papers** — if the task `query` is thin, follow
   the **`emet-prompting`** skill: name a workflow (Target Validation / Safety Assessment / Pathway Analysis),
   pull genetic + expression + perturbation/dependency (DepMap/CRISPR) + pathway + clinical evidence, and ask
   for evidence FOR **and** AGAINST (pleiotropy, inflammation, toxicity, essentiality, expression gap,
   constraint). Capture the risk/against findings into `evidence` too — they matter as much as the supporting ones.
4. **Capture every claim with its PMID/source** (inline `[PMID …]` + the Sources panel). Drop uncited
   claims — never paraphrase or invent a citation. You may model the scrape on `emet/capture.py`
   (`parse_emet_html`) — capture the full text + the `a[href*="pubmed.ncbi.nlm.nih.gov"]` links.

## Write the result envelope — `RohanOnly/emet_queue/results/<id>.json`
```json
{
  "candidate": "<gene from the task>",
  "emet_workflow": "Target Validation | Drug Safety | Pathway Analysis | Quantitative Evidence | Database Q&A",
  "verdict": "no_go | flag | pass",
  "evidence": [{"claim": "...", "source": "Author, Venue Year", "id_or_url": "PMID:########"}],
  "notes": "contradictions / thin-evidence flags",
  "chat_url": "https://emet.benchsci.com/chat/<uuid>",
  "captured_at": "<ISO-8601>",
  "provenance": "emet-live"
}
```
The orchestrator's `emet --live` poller reads exactly this and feeds the `evidence` into the dossier.

## Rules
- Public identifiers only ever cross to EMET. Every claim cited (PMID/source) or dropped.
- Login screen → `{"login_required": true}` result, never auto-login.
- One tab per query; always leave base tab 0 open. Never fabricate — abstain (empty `evidence`) honestly.
