# Plan — Fork LOKA's Chainlit app into `frontend/` as a transparent control surface over `run_live`

*Owner: rohan. Tier: **Feature**. Created 2026-06-24. PLAN step (`sapphire-dev-planner`) for the Feature brief
[`2026-06-24-sapphire-frontend-and-data-planes.md`](2026-06-24-sapphire-frontend-and-data-planes.md). Branch:
`rohan/frontend-loka-fork`. This doc writes no feature code — it sequences buildable, independently-verifiable
tasks.*

> **Direction note (overrides older docs).** `docs/integrations/loka/INTEGRATION_PLAN.md` + `OPEN-QUESTIONS.md`
> describe an HTTP / "don't fork" architecture. That is **superseded**: we **fork** LOKA's Chainlit shell into a
> new `frontend/` dir in *our* repo and bridge **in-process** to `live_engine.run_live(query, ctx=...)`. We still
> honor the **render mapping** (`CONTRACT.md` §3) and the **non-negotiables** (provenance/tier verbatim, two
> planes, no forced consensus, public-IDs-only). The real LOKA repo at
> `/Users/.../drug-discovery-agent` is a **read-only** clone (upstream commit `8685382`) — never modified.

---

## 1. Architecture decision (the fork)

**Directory layout** (all new, all under our repo root; nothing touches `sapphire-orchestrator/` runtime):

```
frontend/
  main.py                 # Chainlit entrypoint (forked from LOKA src/main.py, stripped)
  bridge.py               # in-process bridge: run_live(query, ctx) → list[cl.Element/cl.Step/cl.Message]
  render.py               # pure mapping helpers: run_live dict → Chainlit elements (LOKA _create_*_table pattern)
  starters.py             # reframed CNS starter prompts (was config.yaml starters)
  config.yaml             # app name/title/layout/starters (LOKA-derived, AWS/Bedrock keys removed)
  .chainlit/
    config.toml           # forked from LOKA, custom_css/js kept, telemetry off, no AWS
    translations/         # copied verbatim from LOKA (Chainlit-required)
  public/
    custom.css, custom.js, theme.json, favicon.svg, logo_*.png   # copied from LOKA, re-skinned later
  requirements.txt        # chainlit + pandas ONLY — the frontend's OWN deps (never the engine's)
  FORKED_FROM.md          # provenance: upstream commit, kept/replaced/stripped, attribution
  README.md               # how to run (mock-ctx demo + real)
  tests/
    test_render.py        # pure unit tests on render.py against a captured run_live dict (no Chainlit server)
    fixtures/run_live_mock.json   # a captured mock-ctx run_live output (the render contract fixture)
```

**The bridge (the seam).** `bridge.py` imports `live_engine` from `sapphire-orchestrator/` **in-process**
(add that dir to `sys.path` at import time — the engine is stdlib-only, so importing it pulls in no third-party
deps). The bridge owns:
- `build_ctx(mock: bool)` — returns `None` for the real backends, or the **mock ctx** for offline/demo. The mock
  ctx is the *single source of truth* reused from the tests: `bridge.py` imports `_build_ctx` from
  `sapphire-orchestrator/tests/test_live_engine.py` (or a thin re-export) so the demo path and the test path can
  never drift. **Decision for the human (Q-A below): import the test helper, or lift it into a small shared
  `frontend/mock_ctx.py`?** Recommend: import the test helper directly to guarantee parity.
- `run(query, *, mock)` → calls `run_live(query, ctx=build_ctx(mock))`, returns the raw dict. Never raises
  (run_live's contract); on a hard import/error it returns an honest error envelope the UI renders as an abstain,
  never a fake result.

**How Chainlit launches.** `chainlit run frontend/main.py -w` from repo root (documented in `frontend/README.md`).
`main.py` registers `@cl.on_message` → `bridge.run(...)` → `render.*` → send each element as a `cl.Step`/`cl.Message`.
**No `@cl.data_layer` decorator** → Chainlit falls back to its **default local data layer** (in-memory; no AWS,
no config needed). A **mock toggle** lives as a Chainlit `ChatProfile` ("Demo (mock backends)" vs "Live (real
firm)") so Gate-5 can run the mock path with zero model/network and a human can flip to live.

**Where the mock-ctx hook lives for verification.** Two layers:
1. `frontend/tests/test_render.py` — pure, server-less: loads `fixtures/run_live_mock.json` and asserts every
   render helper emits the right columns/blocks (no Chainlit runtime). This is Gate-1 coverage.
2. The **"Demo (mock backends)" profile** in the running app — Gate-5 launches Chainlit, selects that profile,
   submits a query, and `bridge.run(query, mock=True)` drives a real `run_live` call through `_build_ctx`,
   proving the transparency view renders end-to-end with no external calls.

**Provenance / timing honesty (load-bearing — confirmed against a live mock-ctx run).**
- `discover.agents[]` entries are exactly `{id, status, provenance}` — **there is NO per-agent timing field**.
  The plan renders **only what exists**: id · status (ok/abstained/escalated) · provenance. If overall wall-clock
  is wanted, the bridge may time the *whole* `run_live` call and show one total — but **never** fabricate
  per-agent timings. (Brief says "timing IF available" → it is not available per-agent; render none.)
- Each **fact** carries `value, source, tier, provenance, plane`, and MAY carry `field, confidence, flag`. The
  dossier table columns are **value · field · tier · provenance · plane · flag** (field/flag blank when absent).
- Each **verdict** carries `persona, stance, provenance, status` and (on success) `conviction, rationale,
  fact_claims`; abstain adds `lens`. `consult` has `round1` always and `round2` only sometimes.
- Provenance + tier strings are rendered **verbatim** — never relabel `moat-real`→"internal DB", never upgrade
  a `stub`/`qmodels` chip.

---

## 2. Task list (ordered; each independently verifiable)

Tier key: Trivial / Standard / Feature-slice. Each runs Gate-1 (tests) at minimum; the final task runs Gate-5.

### T1 — Scaffold `frontend/` + fork provenance doc · **Standard**
- **Intent:** Create the `frontend/` dir, copy the *static* LOKA assets we keep, and write `FORKED_FROM.md`.
- **Do:** Copy from the read-only LOKA clone: `.chainlit/config.toml` (+ `translations/`), `public/custom.css`,
  `public/custom.js`, `public/theme.json`, `public/favicon.svg`, `public/logo_*.png`. Strip AWS/Bedrock/RDS from
  `config.toml` is N/A (it has none); set `enable_telemetry = false`. Write `frontend/requirements.txt`
  (`chainlit`, `pandas` — pin to LOKA's `uv.lock`/`pyproject.toml` versions). Write `FORKED_FROM.md`: upstream
  repo `q-state-biosciences/drug-discovery-agent` @ `8685382`; **KEPT** (Chainlit shell, `_create_*_table`
  pattern, css/js); **REPLACED** (Bedrock agent loop → in-process `run_live` bridge); **STRIPPED**
  (`cdk/`, `src/data/dynamo.py`+`s3.py`, RDS perturbation tools, boto3/aioboto3/tiktoken deps); license/attribution
  note (see Risk R3 — no LICENSE file in the source repo; record that and attribute to Q-State Biosciences).
- **DoD:** `frontend/` exists with the assets above; `FORKED_FROM.md` names commit `8685382` and the kept/
  replaced/stripped lists; `requirements.txt` lists chainlit+pandas and **no** boto3/aioboto3/AWS deps.
- **Verify:** `ls frontend/ frontend/.chainlit frontend/public` shows the files; `grep -i boto frontend/requirements.txt`
  returns nothing; `grep 8685382 frontend/FORKED_FROM.md` matches.
- **Constraints:** Read-only on the LOKA clone (copy out, never edit in place). No secrets copied (LOKA `.env`
  excluded — Gate-3).
- **Files:** `frontend/.chainlit/*`, `frontend/public/*`, `frontend/requirements.txt`, `frontend/FORKED_FROM.md`.

### T2 — Capture the render fixture (a real mock-ctx `run_live` dict) · **Trivial**
- **Intent:** Freeze a real `run_live` mock-ctx output as the render contract fixture so render tests are grounded
  in the actual shape, not a hand-written guess.
- **Do:** A tiny `frontend/tests/_capture_fixture.py` (or a documented one-liner) runs `run_live` through
  `_build_ctx` and writes the dict to `fixtures/run_live_mock.json`. Capture for a CNS query that exercises the
  panel (e.g. "Is TSC2 a viable target in tuberous sclerosis?"). Commit the JSON.
- **DoD:** `fixtures/run_live_mock.json` exists and validates against `run_live_schema.py`
  (`validate_run_live(json) == []`); it contains `discover.dossier`, `discover.agents`, `consult.round1`,
  `synthesize`.
- **Verify:** `python -c "import json; from contracts.run_live_schema import validate_run_live; print(validate_run_live(json.load(open('frontend/tests/fixtures/run_live_mock.json'))))"` → `[]` (run with
  `sapphire-orchestrator` on path).
- **Constraints:** The fixture is captured, **never hand-edited** to fake fields (provenance honesty).
- **Files:** `frontend/tests/fixtures/run_live_mock.json`, `frontend/tests/_capture_fixture.py`.
- **Depends on:** T1.

### T3 — `render.py`: dossier + planes + flags · **Feature-slice**
- **Intent:** Pure functions mapping `discover` → Chainlit elements, with the two data planes rendered distinctly.
- **Do:** Reusing LOKA's `_create_*_table` pattern (`cl.Dataframe`):
  - `render_dossier(discover)` → **two** `cl.Dataframe`s (or two clearly-titled sections): **"Internal plane
    (Quiver moat)"** for `plane=="internal"` facts and **"External plane (public evidence)"** for
    `plane=="external"`. Columns: **value · field · tier · provenance · source · flag** (per CONTRACT §3; `plane`
    is the section, not a column — or keep a `plane` column too; recommend section split = the distinct render).
  - `render_flags(discover.flags)` → a ⛔ **VETO** callout, a ⚠ **DIVERGENCE** callout ("internal vs external —
    surfaced, not reconciled; often the alpha"), a muted **KNOWN_UNKNOWNS** list. Empty lists render nothing.
  - `render_agents(discover.agents)` → a small "firm roster" table: **id · status · provenance**; abstained/
    escalated agents shown explicitly (honesty), NOT hidden. **No timing column** (it does not exist).
- **DoD:** Given the T2 fixture, the functions return Chainlit elements with the exact columns; internal vs
  external facts land in separate sections; abstained agents appear; tier/provenance strings are verbatim from
  the fixture.
- **Verify:** `python -m unittest frontend.tests.test_render` asserts: (a) two plane sections exist when both
  planes present; (b) column headers == the 6 required; (c) an abstained agent (inject one in a fixture variant)
  shows status `abstained`; (d) no test references a timing field.
- **Constraints:** Pure functions (no Chainlit server, no I/O). Verbatim tier/provenance. Render only existing
  fields.
- **Files:** `frontend/render.py`, `frontend/tests/test_render.py`.
- **Depends on:** T2.

### T4 — `render.py`: roundtable spread + synthesis · **Feature-slice**
- **Intent:** Map `consult` (round1 [+round2]) and `synthesize` → Chainlit elements showing the **spread**, no
  forced consensus.
- **Do:**
  - `render_roundtable(consult)` → one `cl.Step`/card **per verdict** titled by `persona`; headline =
    `stance · conviction` (e.g. "conditional · 3"); body = `rationale`; `fact_claims` rendered as citations back
    into the dossier. **Do NOT collapse to a single consensus.** When `round2` is present, render it as a
    **rebuttal progression** (round2 reacts to round1) — e.g. a second column/section per persona. Abstained
    verdicts (`status!="ok"`, with `lens`) shown explicitly.
  - `render_synthesis(synthesize)` → `recommendation` headline · `confidence` chip · `proposed_experiment`
    callout (hands off to Experiment-Design) · `entities` tags. Framed as "facts + how each player reacted," not
    a verdict.
- **DoD:** Given the fixture, one element per persona; the spread is preserved (N personas → N cards); a fixture
  with `round2` renders the progression; synthesis shows all four parts.
- **Verify:** `python -m unittest frontend.tests.test_render` (extended): assert verdict-card count ==
  `len(round1)`; assert a `round2` fixture variant renders both rounds; assert synthesis includes
  recommendation/confidence/experiment/entities; assert no consensus-collapse (no single merged verdict).
- **Constraints:** No forced consensus. Personas cite facts, never invent them (render `fact_claims` as cites,
  don't synthesize new claims).
- **Files:** `frontend/render.py`, `frontend/tests/test_render.py`.
- **Depends on:** T3.

### T5 — `render.py`: plan + header/footer · **Standard**
- **Intent:** Render `query` (header), `plan` (collapsed "how the firm scoped this" step), and `engagement_id`
  (footer, for auditability). `priors`/`reflection` low-priority/optional.
- **Do:** `render_plan(plan)` → a collapsed `cl.Step` listing `deliverable, disease, modality, agents[], panel[]`.
  `render_header(query)` / `render_footer(engagement_id)`.
- **DoD:** Given the fixture, the plan step lists the scoped agents/panel; the footer surfaces the `eng_…` id.
- **Verify:** unittest asserts plan step contains the agent ids and the engagement_id appears in the footer
  element.
- **Files:** `frontend/render.py`, `frontend/tests/test_render.py`.
- **Depends on:** T2.

### T6 — `bridge.py`: in-process `run_live` seam + mock ctx · **Feature-slice**
- **Intent:** The bridge that imports the engine in-process and exposes `run(query, *, mock)`.
- **Do:** Add `sapphire-orchestrator/` (and its `tests/` for `_build_ctx`) to `sys.path`; `from live_engine import
  run_live`. `build_ctx(mock)` → `_build_ctx()` when mock else `None`. `run(query, mock)` returns the dict;
  wraps the call to never propagate an exception (honest error envelope). Time the whole call → expose one
  total-wall-clock number (allowed; per-agent is not).
- **DoD:** `bridge.run("…", mock=True)` returns a dict that passes `validate_run_live(...) == []`; importing
  `bridge` pulls in **no** third-party package beyond what the engine already needs (engine is stdlib).
- **Verify:** `python -c "import sys; sys.path.insert(0,'frontend'); import bridge; r=bridge.run('Is TSC2 a viable target?', mock=True); from contracts.run_live_schema import validate_run_live; print(validate_run_live(r))"` → `[]`. And a negative probe: `bridge.run('', mock=True)` returns a well-formed (possibly degraded) dict,
  not a traceback.
- **Constraints:** **Stdlib boundary** — `bridge.py` must not add engine deps; chainlit/pandas stay frontend-only.
  Mock ctx imported from the test helper to guarantee parity (no second copy of the mocks).
- **Files:** `frontend/bridge.py`, `frontend/tests/test_bridge.py`.
- **Depends on:** T1 (for dir), independent of render.

### T7 — `main.py` + `starters.py`: Chainlit wiring + CNS starters + mock/live profiles · **Feature-slice**
- **Intent:** The Chainlit entrypoint that wires `@cl.on_message` → bridge → render, with reframed CNS starters
  and a Demo/Live `ChatProfile` toggle. **No** AWS data layer.
- **Do:** Fork LOKA `src/main.py` but **strip**: boto3/dynamo/s3 imports, `@cl.data_layer`, `on_chat_resume`
  S3 restore, the CSV-upload/dataframe-tool path, Bedrock `get_model_id`. **Keep:** `@cl.set_starters` (from
  `starters.py`), `@cl.set_chat_profiles` repurposed to **"Demo (mock backends)" / "Live (real firm)"**,
  `@cl.on_message`. On message: `cl.Step("Convening the firm…")` spinner → `bridge.run(query, mock=profile=="Demo")`
  → emit `render.render_plan`, `render_agents`, `render_dossier`, `render_flags`, `render_roundtable`,
  `render_synthesis`, footer. `starters.py` = 4–6 CNS-reframed starters (e.g. "Is TSC2 a viable CNS target in
  tuberous sclerosis?", "Would FDA/payers back an ASO for SCN2A DEE?").
- **DoD:** `chainlit run frontend/main.py` boots; selecting "Demo" + submitting a starter renders the full
  transparency view; no AWS/boto import anywhere in `frontend/main.py`.
- **Verify:** Covered by Gate-5 (T9) for the live render; here, `python -c "import ast,sys; ast.parse(open('frontend/main.py').read())"` + `grep -i 'boto\|dynamo\|s3\|bedrock' frontend/main.py` returns nothing;
  starters count ≥ 4 and are CNS-themed.
- **Constraints:** Default local data layer (omit `@cl.data_layer`). Public-IDs-only note in starters (no
  internal IDs in prompts). Stdlib boundary unaffected (chainlit is frontend-only).
- **Files:** `frontend/main.py`, `frontend/starters.py`, `frontend/config.yaml`.
- **Depends on:** T3, T4, T5, T6.

### T8 — Retire `site/` as the destination (doc only, no deletion) · **Trivial**
- **Intent:** Record that `frontend/` supersedes `site/` as the front face, without blindly deleting `site/`.
- **Do:** Add a note at the top of `site/README.md` (and a line in `docs/README.md` / `status/OVERALL.md` if
  appropriate) — "**Superseded** by `frontend/` (LOKA-fork Chainlit control surface) as of 2026-06-24; `site/`
  retained as the canned demo until `frontend/` covers it." Do NOT remove `site/`.
- **DoD:** `site/README.md` carries the superseded banner; no files deleted.
- **Verify:** `grep -i superseded site/README.md` matches; `git status` shows no deletions.
- **Files:** `site/README.md`, `docs/README.md` (note line).

### T9 — Gate-5 functional verification + run docs · **Feature-slice**
- **Intent:** Prove the transparency view actually renders end-to-end through `run_live` (mock ctx), adversarially;
  document the real-run path.
- **Do:** Launch Chainlit headless/locally, select "Demo (mock backends)", submit a CNS query, and confirm the
  rendered elements: plan step, agent roster (with provenance, incl. any abstained), **two plane sections**
  (internal/external) with the 6 columns, VETO/DIVERGENCE/KNOWN_UNKNOWNS blocks (present-or-empty), roundtable
  **spread** (N persona cards, no consensus collapse), synthesis. Adversarial probes: empty query; a query with
  no moat hit (degraded dossier → abstained agents shown); confirm no traceback reaches the UI. Write
  `frontend/README.md`: (a) the **mock demo** command (`chainlit run frontend/main.py`, pick Demo); (b) the
  **real** run — pick "Live", note `run_live` needs the `claude` CLI for live persona/fact subagents (and
  optionally the EMET Playwright skill + the moat SQLite at `RohanOnly/moat/moat.sqlite`); without a model the
  live path abstains honestly (it does not crash).
- **DoD:** A verifier (`sapphire-dev-verifier`, independent) confirms the observable behavior matches the claim:
  the firm process renders, planes are distinct, the spread is preserved, abstains are visible, garbage input
  degrades gracefully. `README.md` documents both run modes.
- **Verify:** `chainlit run frontend/main.py` (Demo profile) → screenshot/snapshot showing the six render
  regions; the empty-query and no-hit probes render a degraded-but-well-formed view (no stack trace). Plus the
  full suite green (Gate-1) and the stdlib grep (Gate-4) over the engine.
- **Constraints:** This is the gate that "tests pass" cannot replace — it must LAUNCH the app, not just run unit
  tests. Use the **same** `_build_ctx` the offline tests use (parity).
- **Files:** `frontend/README.md`, plus the verifier's evidence in the PR.
- **Depends on:** T7 (and all prior).

---

## 3. Sequencing & parallelism

```
T1 ──┬─> T2 ──┬─> T3 ──> T4 ─┐
     │        ├─> T5 ───────┤
     └────────────> T6 ─────┼─> T7 ──> T9 (Gate-5)
                            │
T8 (independent doc) ───────┘  (can land any time)
```
- **Serial spine:** T1 → T2 → (T3, T5 parallel after T2; T4 after T3) and T6 (parallel after T1) → T7 → T9.
- **Parallelizable:** T5 alongside T3/T4; T6 alongside the render tasks; T8 anytime.
- Each render task (T3/T4/T5) is one reviewable diff against the same `render.py` + its tests — keep them
  separate commits so Gate-2 review stays small.

---

## 4. Risks & unknowns

- **R1 — No per-agent timing (confirmed).** `discover.agents[]` = `{id, status, provenance}` only; a live mock-ctx
  run confirms no timing field. **Decision: render id·status·provenance; optionally one total wall-clock from the
  bridge; never fabricate per-agent timing.** The brief's "timing IF available" resolves to *not available per
  agent*.
- **R2 — Chainlit default data layer.** Omitting `@cl.data_layer` uses Chainlit's in-memory local layer — **no
  config needed**; threads/persistence are ephemeral (fine for a control surface). If durable history is later
  wanted, that's a separate, scoped task (SQLite data layer) — OUT of scope here.
- **R3 — License / attribution.** The LOKA clone has **no `LICENSE` file** and no license field in
  `pyproject.toml`/`README` (it's a Q-State Biosciences internal repo). `FORKED_FROM.md` must state this honestly:
  forked from an internal Q-State repo @ `8685382`, attribute to Q-State Biosciences, and **flag for a human**
  whether explicit permission/license text is required before this ships externally (see Q-C).
- **R4 — Chainlit version pin.** LOKA's `config.toml` `generated_by = "2.0.2"`. Pin `chainlit==2.0.2` (or the
  exact `uv.lock` version) in `frontend/requirements.txt` so the forked `config.toml`/`custom.js` selectors stay
  valid. `custom.js` targets fragile DOM class selectors (`[class*="MessageContainer"]`) — a Chainlit upgrade can
  break the welcome-screen injection. Keep the version pinned; re-skin is a later task.
- **R5 — `run_live` latency on the live path.** A real harnessed run is slow (multi-agent, possibly live EMET);
  there is no token stream. The UI must show a `cl.Step` spinner and the verifier should test the **mock** path
  (fast, deterministic) for Gate-5; the live path is documented, not gated, in this PR.
- **R6 — sys.path import of the engine.** The bridge importing `live_engine` cross-dir is slightly fragile.
  Mitigate by computing the path relative to `frontend/bridge.py` (`Path(__file__).parents[1] /
  "sapphire-orchestrator"`), not a hardcoded abs path. Confirm the engine stays stdlib so the frontend process's
  third-party deps never leak into engine imports.
- **R7 — `round2` may be absent.** The contract has `consult.round1` always, `round2` sometimes; the mock-ctx
  fixture shows `round1` only. T4 must render the progression **when present** and degrade cleanly when absent;
  capture a `round2` fixture variant if one can be produced offline, else assert the absent-path renders round1
  alone (do not fabricate a round2).

---

## 5. Open questions for the human (genuine forks — decide before building)

- **Q-A — Mock-ctx source.** Import `_build_ctx` directly from `sapphire-orchestrator/tests/test_live_engine.py`
  (guarantees parity, but couples the frontend demo to a test module), **or** lift the mock backends into a small
  shared `frontend/mock_ctx.py` (cleaner layering, risk of drift)? *Recommend: import the test helper.*
- **Q-B — Planes: section split vs. column.** Render internal/external as **two separate titled tables/sections**
  (most "distinct"), or one table with a bold **plane** column? *Recommend: two sections (the brief stresses
  "render the two data planes distinctly").*
- **Q-C — Attribution/permission.** The LOKA source has no license file (internal Q-State repo). Is explicit
  written permission / a license header required before `frontend/` (a fork of it) ships, or is internal reuse
  within Quiver sufficient? *Needs a human call (R3).*
- **Q-D — Live-path gating.** Do we gate Gate-5 on the **mock** path only (recommended — deterministic, $0), and
  document the live path as a manual run? Or must a real `claude`-CLI live run be demonstrated in this PR? *
  Recommend: gate on mock, document live.*

---

## 6. Explicitly OUT of scope
- Routing logic (when to call the firm vs. LOKA's fast tools — CONTRACT §4): the fork has no LOKA tools left, so
  every query goes to `run_live`. A router belongs to a later task.
- Durable chat history / SQLite data layer (R2).
- Re-skinning `public/` css/js to Sapphire branding beyond keeping LOKA's (a polish task).
- Deleting `site/` (T8 only marks it superseded).
- Wiring the ASO-Design tool to feed sequences into `aso-tox` (separate roadmap item).
- Any change to `sapphire-orchestrator/` runtime, `run_live`, or the contract (the fork consumes the contract
  as-is; if a new field is needed it's a separate contract-change task per `run_live_schema.md` §Stability).

---

## 7. Files the builder will touch (all absolute under repo root)
- New: `/Users/rohanaryagondi/Desktop/Projects/Quiver/sapphire-capability-map/frontend/**`
- Edited (doc only): `/Users/.../sapphire-capability-map/site/README.md`, `/Users/.../docs/README.md`
- Read-only references (never edited): the LOKA clone at
  `/Users/rohanaryagondi/Desktop/Projects/Quiver/drug-discovery-agent` (@ `8685382`);
  `/Users/.../sapphire-orchestrator/contracts/run_live_schema.{md,py}`;
  `/Users/.../sapphire-orchestrator/tests/test_live_engine.py` (`_build_ctx`);
  `/Users/.../docs/integrations/loka/CONTRACT.md`.
