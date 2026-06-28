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

### D5 — Trigger policy for design tools: auto vs explicit · OPEN
Should design auto-fire when a target validates, or only on an explicit design ask?
- **Recommendation:** **explicit, gated by capability class** for now — auto-firing a ~3 hr / real-$ EC2
  job on every diligence query is dangerous. The Engagement Lead proposes design as a *next step*; it runs
  when the engagement's class includes `design`.

### D6 — Sequencing: make the live engine whole before or after front-door convergence? · LEANING
Gaps (`status/SAPPHIRE_GAPS.md`): round-2 + spread missing in `run_live`, 6 semantic agents not dispatched,
VETO not gated.
- **Recommendation:** **before** — close these first (small, contract-supported), *then* converge the front
  door onto the now-complete path. Order: D6 → D1 → ASO Design seam.

### D7 — Credentials: rotate + history scrub? · OPEN (pending your call from earlier)
The forward scrub + scanner coverage shipped on `rohan/harness-hardening`. Still open: (a) rotate the EMET
password (13/14 chars were in tracked files / git history), and (b) whether to rewrite git history to purge
the prior occurrences (destructive; affects the team). Private repo lowers urgency but it's your #1 stated
constraint.
- **Recommendation:** rotate the EMET password (cheap, decisive); defer history rewrite unless the repo
  visibility changes.

### D8 — Loka's role: build the front door on Loka, or keep the custom consoles? · OPEN
The sprint deck calls Loka "the front-end / orchestrator scaffold." Today the live surface is our own
consoles (`frontend2/`, `orchestrator_ui/`).
- **Question for you:** is Loka mature/owned enough to be the front door we build on (and we adapt the seam
  to it), or do the custom consoles remain the surface and Loka is a future target? This changes where D1's
  "one live path" terminates. Needs your read on Loka's status. See [`docs/LOKA.md`](../LOKA.md).

---

## Decided (move items here as they resolve)
*(none yet)*
