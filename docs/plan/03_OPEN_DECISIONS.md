# 03 — Open architecture decisions (the decision log)

Cross-cutting decisions we need to make as the build grows. Each has a recommendation; nothing here is
settled until you sign off. When one is decided: mark it RESOLVED, record the choice + date, and fold the
consequence into the relevant plan doc. This is where "we ideate and flesh out" converges into commitments.

> Legend: **OPEN** (needs your call) · **LEANING** (recommendation, pending sign-off) · **RESOLVED**.

---

### D1 — Front-door convergence: which single live path? · LEANING
There are three live paths (canned `orchestrator.run`, harnessed `live_engine.run_live`, `claude -p`
`orchestrator_ui` :8101). They diverge in capability and that's the keystone risk.
- **Options:** (a) harnessed `run_live` is the one true path; (b) the `claude -p` console is; (c) keep all
  three explicitly labeled.
- **Recommendation:** **(a)** — make `run_live` (guard-enforced, schema-validated, provenance-stamped,
  traced) the single path behind the front door; keep canned as the $0 replay/demo mode; demote/retire the
  `claude -p` console to an experimental surface. Rationale: only `run_live` carries the data-boundary +
  provenance guarantees end-to-end.
- **Blocked by:** D6 (the live engine must be made whole first, else converging onto a weaker path).

### D2 — Adopt the three capability classes (evidence / design / experiment)? · LEANING
The blueprint ([`00`](00_FULL_FLOW.md)) is organized around this split.
- **Recommendation:** **Yes.** It's the through-line that keeps tool growth coherent and tells the
  Engagement Lead what to activate. Low cost (it's a classification + an `class` field on the registry).

### D3 — ASO Design execution shape: bundled EC2 vs staged · OPEN
See [`02 §4`](02_ASO_DESIGN.md). Bundled (one AMI runs 01→07) vs staged (light stages local, off-target on
EC2).
- **Recommendation:** **bundled v1** (one ledgered AWS job → one envelope; simplest seam), optimize to
  staged later if cost/latency demands. **Your call** — depends on how much you want to invest in the AMI
  vs the seam's stage-sequencing.

### D4 — Where do design assets live? · OPEN
Candidate sets (e.g. 20 ASOs + annotations, or larger libraries) can be sizable and are real artifacts.
- **Options:** (a) inline in the dossier; (b) a small **artifact registry** (`RohanOnly/assets/<run_ref>/`)
  with the dossier carrying a reference + the shortlist.
- **Recommendation:** **(b)** — keep the dossier lean; assets are referenced, not embedded. Mirrors how
  Q-Models run artifacts are ledgered.

### D5 — Trigger policy for design tools: auto vs explicit · ✅ RESOLVED (2026-06-28)
**Decision: explicit design ask only.** Design tools fire only when the engagement's ask is a design
request (capability class includes `design`); they never auto-fire on a diligence query. The Engagement Lead
may *propose* design as a next step, but a ~3 hr / real-$ EC2 job runs only on an explicit ask.

### D6 — Sequencing: make the live engine whole before or after front-door convergence? · LEANING
Gaps (`status/SAPPHIRE_GAPS.md`): round-2 + spread missing in `run_live`, 6 semantic agents not dispatched,
VETO not gated.
- **Recommendation:** **before** — close these first (small, contract-supported), *then* converge the front
  door onto the now-complete path. Order: D6 → D1 → ASO Design seam.

### D7 — Credentials: rotate + history scrub? · ✅ RESOLVED (2026-06-28)
**Decision: leave the EMET password as-is (no rotation) and do not rewrite git history for now.** The
forward scrub + scanner coverage shipped (PR #110); the private-repo blast radius is acceptable. Revisit only
if repo visibility changes.

### D8 — Loka's role: build on Loka, or keep our own consoles? · ✅ RESOLVED (2026-06-28)
**Decision: do NOT build the front door on Loka's code; reuse Loka's DATA + DESIGNS, keep our own consoles.**
Loka's app is a private repo (`q-state-biosciences/drug-discovery-agent`) we'd have to request, and it is a
*single-agent* Bedrock/Chainlit PoC that Sapphire's multi-agent firm (orchestrator + harness + EMET +
Q-Models) already **supersets** — building on it is friction for little gain ("too much trouble"). What we
keep from Loka:
- **Data (in hand, already wired):** the CNS_DFP perturbation-distance parquet = our real moat (`moat-real`).
- **Designs to adopt:** the 4 perturbation workflows (gene/drug × gene/drug; similar=mimic / opposite=rescue),
  the persisted-scratchpad pattern, and their LLM-as-judge eval harness.
- **Cheap, high-value artifacts to REQUEST from Quiver** — these fix a real gap (our raw EP-antipodal distance
  does *not* reproduce Loka's flagship "rapamycin rescues TSC2" because Loka layers extra scoring on the raw
  distance): the **7-stage target-ID workflow doc + the rescue scoring weights** (≈40% phenotypic rescue /
  30% mechanistic / 30% safety), and the repo for *reference only*.
**Consequence for D1:** the single live path terminates at **our consoles**, not Loka. See [`docs/LOKA.md`](../LOKA.md).

---

## Decided
- **D5 (2026-06-28)** — design tools fire on an **explicit design ask only**, never auto on diligence.
- **D7 (2026-06-28)** — **leave the EMET password** (no rotation), no history rewrite; forward scrub shipped (PR #110).
- **D8 (2026-06-28)** — **don't build on Loka's code**; reuse its data (done) + designs; request the scoring-weights
  doc; our consoles stay the surface.
