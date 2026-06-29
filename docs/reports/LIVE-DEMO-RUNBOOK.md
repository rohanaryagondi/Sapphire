# Sapphire — Live Demo Runbook + State Handoff

*Written 2026-06-25 by Head Claude. For a fresh Head Claude session that will run the live demo via
**computer use** (driving the browser/UI directly), with **Playwright reserved for the EMET agent**.
Read `CLAUDE.md` and `sapphire-orchestrator/AGENTS.md` first, then this.*

---

## 1. What Sapphire is (one paragraph)

A two-bucket agentic CNS drug-discovery decision firm. **Bucket-1 (facts)** gathers a *cited fact
dossier* — the Quiver internal moat, EMET (BenchSci) published evidence, Q-Models, quant seams, and
semantic corpora — iterating until complete (gap/contradiction/VETO/DIVERGENCE checks). **Bucket-2
(deliberation)** is a roundtable of persona partners who debate the dossier (independent verdicts →
moderated rebuttal); **no forced consensus — the spread is the product.** Synthesis = the facts + how
each player reacted. Engine: `sapphire-orchestrator/live_engine.py::run_live`.

## 2. Current state — what is REAL vs SIMULATED vs CAPTURED (be honest, label everything)

| Component | State |
|---|---|
| Internal moat (CNS_DFP) | ✅ **REAL** — `RohanOnly/moat/moat.sqlite`; 8 real TSC2 EP-signatures (TSC1~TSC2 KO cos 0.083; rescue candidates Isorhamnetin 0.253, GW-406381, Momelotinib, Cyclothiazide) |
| EMET / PMIDs | ✅ **REAL** via the **session-bridge** (orchestrator drives EMET in its authenticated browser → captured envelope → injected). Captured TSC2 envelope = 9 real PMIDs. |
| Boltz (structure/affinity) | ✅ **REAL** — hosted API (`api.boltz.bio`), wired into Bucket-1 (#80 seam + #82 firm-wire). Fires on a structure/affinity input. **Async fold takes ~30s–few min.** |
| Q-Models — CPU | ✅ **REAL** (`live-local`, $0) |
| Q-Models — GPU/AWS | ⏸️ **SET ASIDE** for now (proven once, ~$0.13; not part of the current demo) |
| Quant seams (aso-tox · gnomad · gtex · interpro · gprofiler · robyn-scs) | ✅ **REAL** python seams |
| Corpora (semantic agents' facts) | ✅ **REAL** — Hayes **4/6** (patent-ip, dea-scheduling, clinical-trial-registry, post-market-safety) |
| Roundtable + claude fact-agent reasoning | 🧪 **SIMULATED** (clearly labeled, `provenance=simulated`) — real models pending the user's decision |
| Engine / synthesis / flags / harness | ✅ **REAL** |
| Front-end 3-pane UI | 🎨 in Gavin's design track (`docs/design/console-ui/`, PRs in flight) |

## 3. How to run the live demo

**Front-end:** the LOKA Chainlit fork at `frontend/`. Run:
```bash
cd frontend && chainlit run main.py --port 8000      # → http://localhost:8000
```
Open in a browser **via computer use** (so the user watches the live step-tree). The app is on the
**live harnessed path** (`bridge.run → live_engine.run_live`).

**Required local data (gitignored, under `RohanOnly/` — never commit):**
- `RohanOnly/moat/moat.sqlite` — the real moat (without it, moat degrades to empty, honestly).
- `RohanOnly/boltz_api.env` — `BOLTZ_API_KEY=...` (Boltz hosted API). Read at call time only.
- `RohanOnly/emet_creds.env` + `RohanOnly/emet_profile/` — for live EMET capture (auto-login profile).

**Profiles (top-left selector):**
- `Demo (mock backends)` — deterministic, $0, no external calls.
- `Live (real firm)` — real backends; needs the `claude` CLI for personas (slow).
- `Live (cheap · haiku)` — real backends, haiku personas.
- **`Live (demo · simulated models)`** — **the demo profile**: real moat + real EMET + real seams/Boltz + 🧪-simulated personas (fast, honest). **Use this.**
- `Replay (captured TSC2 · $0)` and `Replay (TSC2 · session-bridge EMET · $0)` — frozen real runs (real moat + real EMET PMIDs + a real haiku spread), instant + deterministic. Great fallback / guaranteed-visible demo.

**EMET in a Live run:** `bridge.run` auto-loads the captured envelope for the run's candidate from
`sapphire-orchestrator/scenarios/emet_envelopes/<CANDIDATE>.json` → real `emet-live` PMIDs land. TSC2
is covered. An **uncovered** candidate honestly abstains (login_required → escalate) — never fabricates.

**Boltz in a Live run:** fires when a structure/affinity input is present:
- **Structure-only** (front-end-ready): include a **≥25-aa protein sequence** in the query → the
  query-text extractor (`live_engine._extract_structure_inputs`) triggers a Boltz fold.
- **Binding** (target + ligand): via the explicit `structure={target_sequence, ligand_smiles}` channel
  — currently **engine-level** (`run_live(structure=...)`); the front-end `bridge.run` does **not** yet
  expose `structure=` (it exposes `sequences` for ASO + `emet_envelopes` for EMET). **Gap to close** if a
  click-the-button binding demo is wanted; until then drive binding via the engine or add a `structure=`
  pass-through to `bridge.run`.

## 4. Recommended demo flow

1. **Bring up the front-end** (computer use), pick **`Live (demo · simulated models)`**.
2. **The TSC2 decision:** ask *"Is TSC2 a viable target in tuberous sclerosis?"* → watch the step-tree
   stream: plan → **moat (8 real)** → **EMET (9 real PMIDs)** → seams → semantic (🧪) → flags →
   roundtable (🧪 spread) → **synthesis "Conditional advance · medium."** This is the flagship — real
   internal + real published evidence, the spread, full transparency.
3. **Boltz (the structural check):** the compelling, coherent demo is **moat → Boltz** — fold a
   **moat-surfaced rescue candidate against the mTOR-axis anchor**. Verified working:
   **FKBP12 (UniProt P62942, 108 aa) + Isorhamnetin** (PubChem CID 5281654, the #1 moat rescue hit) →
   live `api.boltz.bio` returned **structure_confidence 0.88, pTM 0.93, ipTM 0.78** (high-confidence
   fold), **binding_confidence 0.51** (borderline — honest; isorhamnetin isn't a known FKBP12 ligand and
   the model didn't over-call it). ~72s, ~$0.025. Run it via the `structure=` channel (engine) or the
   front-end if/once `structure=` is wired.
4. **Real fresh EMET (optional, via Playwright):** the EMET agent uses Playwright + the hardened
   **DOM-scrape capture** (`python -m emet.capture --candidate TSC2 --query "..."`) → writes
   `scenarios/emet_envelopes/TSC2.json` → the next Live run uses it. (See §5.)

## 5. EMET architecture (important — read before touching EMET)

- **The path that works: the session-bridge** (`sapphire-orchestrator/emet/session_bridge.py`). The
  orchestrator drives EMET in its **own authenticated browser**, captures one envelope per candidate,
  and injects via `make_session_emet_handler(envelopes)` → `run_live` (it `setdefault`s, so the injected
  handler wins). Real cited PMIDs, no fabrication, honest-abstain for uncovered candidates.
- **Hardened capture (#91, `emet/capture.py`):** a **deterministic Playwright DOM-scrape** (NO LLM) —
  submit the query, wait for the answer, scrape the answer `<article>` + the Sources panel
  (`a[href*="pubmed.ncbi.nlm.nih.gov"]` → PMID; `a[href*="doi.org"]` → DOI) → envelope. Pure parser
  `parse_emet_html(...)` is stdlib + unit-tested on fixtures; the live driver lazily imports Playwright.
  Selectors that matter (discovered live; the canned protocol was stale): type into the **`.tiptap`
  wrapper** (not `.tiptap p`); the send control is a **clickable `<div>` wrapping `.lucide-arrow-up`**
  (not a `<button>`); detect login by URL/password-field, not a bare `auth0` substring.
- **SHELVED — the `claude -p` EMET runner** (`emet/handler.py::_default_runner`): three iterations
  (headless profile #77 → CDP #84 → CDP+sonnet) all **tool-fail / are too slow** (the headless agent
  drives BenchSci's agentic UI unreliably; ~8–9 min, escalates). Kept only as a documented non-default
  fallback. **Do not rely on it.**
- **Why:** there is **no EMET-MCP for ~1 week**. Until then, session-bridge + DOM-scrape (Playwright,
  authenticated profile) is the real-EMET path. **The EMET agent is the one place Playwright is used.**

## 6. Boltz (hosted API)

- Seam: `sapphire-orchestrator/tools/boltz_seam.py` (stdlib `urllib`, no SDK). Key from
  `RohanOnly/boltz_api.env`. Provider: Boltz Compute, `api.boltz.bio/compute/v1`, header `x-api-key`,
  **async** (`POST /predictions/structure-and-binding` → poll). Public identifiers only
  (sequences/SMILES) — the seam's `assert_public_only()` + the `data_boundary` guardrail block internal
  data. Wired into Bucket-1 in `live_engine.py` (#82); honest-degrades to KNOWN_UNKNOWN on missing
  key/error/timeout (never fabricates a structure/affinity number).

## 7. Hard rules (non-negotiable)

- **Honesty / no oversell:** label REAL vs 🧪 SIMULATED vs CAPTURED everywhere it renders. Never present
  simulated reasoning as a real model verdict; never present a captured envelope as a fresh live drive
  without saying so. Mark `proven` vs `paper-claim`. EMET/Boltz **abstain** rather than fabricate.
- **Data boundary:** only public identifiers (gene symbols, SMILES, disease terms, sequences) ever leave
  to EMET / web / Boltz / Q-Models. Internal moat scores/IDs never do.
- **Credentials off GitHub:** `RohanOnly/` is gitignored; the EMET creds + Boltz key live there. Never
  commit a secret; grep diffs before any commit.
- **DIVERGENCE (internal↔external) is surfaced, not auto-reconciled** — often the alpha.

## 8. The dev harness (Head Claude is also the approver)

Sapphire is built by a 3-person team (rohan · hayes · gavin), each driving a Claude. Contributors work
feature branches; **only Head Claude (rohan's) reviews/gates/merges PRs**. To gate: an **isolated git
worktree** (never disturb the main working tree — another session may be building there) → full suite
(`bash dev/run-tests.sh`) + the relevant gate (corpus PRs: `dev/validate-corpus.sh`; code PRs:
review + Gate-5 functional verification) + provenance/secrets/binaries + stdlib-engine boundary → merge
(squash, delete branch) only if all-green, else comment + hold. Ledger + workboard on merge (via a
worktree off main; `--no-verify` is the sanctioned approver path since the pre-push hook blocks direct
main pushes — disclose it). Monitors (commit-watcher, PR-open) + a backup cron sweep drive the loop.
Note a documented load-flake: `tests/test_live_engine.py::test_consult_round1_non_empty_and_stamped`
goes RED under heavy CPU, green when idle — re-run isolated; don't fail a gate on it alone.

## 9. In-flight as of this handoff (2026-06-25)

- **Merged today (~14 PRs):** EMET session-bridge front-end (#90, supersedes #77/#84) · Boltz seam (#80)
  + firm-wire (#82) · AWS infra (#81, set aside) · Q-Models GPU code (#86, set aside) · 4 corpora
  (#76/#83/#85/#87) · site polish (#79) · 3 test/validator fixes (#88/#89) · design artifacts.
- **Open PRs to gate:** **#91** (EMET DOM-scrape hardening — real capture got 14 PMIDs, 600 green),
  **#93** (Gavin's chat-first console UI `sapphire_chat.html`). Gate per §8.
- **Demo infra left running:** a front-end on `:8000` from a worktree of main at `/tmp/fe-demo`
  (symlinked `RohanOnly/`). Several `/tmp/*` worktrees from gating subagents — `git worktree prune` +
  clean `/tmp` as needed. A stray screenshot `demo-tsc2-frontend.png` may exist in a worktree.
- **HELP queue:** effectively clear (boto3, validate-corpus `/tmp`, patent-T1 all resolved; only a stale,
  already-satisfied robyn-scs note remains).

## 10. Honest gaps (state these to the user)

1. **Real model reasoning** (roundtable + claude fact-agents) is simulated — pending the user's call.
2. **EMET is captured-session** (orchestrator-driven), not a pure click-the-button-live front-end (the
   Python front-end can't drive a browser). **Computer use lets the orchestrator drive it for the demo.**
3. **Boltz binding from the front-end** needs a `structure=` pass-through in `bridge.run` (engine path
   works today). Structure-only Boltz works from the front-end via a sequence in the query.
4. **Q-Models GPU/AWS** is set aside.
