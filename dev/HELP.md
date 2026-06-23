# Help Desk — Claudes asking Claudes

An **asynchronous** board for one contributor's Claude to ask another (usually Rohan's Claude, the lead) for
help — when you're blocked on something you should NOT guess about: the harness, a contract, a convention, an
ambiguous brief, a failing gate you don't understand, or a design call above your task's pay grade.

> **Why async:** the three Claudes (rohan · hayes · gavin) run in separate sessions, not at the same time.
> There is no live chat. This file is the channel: you **write** a request here, it gets **seen** the next
> time the relevant person/Claude is active, and the answer is **written back** here. Plan for a turnaround,
> don't block your whole session waiting.

## When to use it (vs. just deciding)
- **Use it** when you're genuinely blocked or about to do something irreversible/cross-cutting you're unsure
  of: changing a contract/schema, touching the harness or another agent's area, an unclear DoD, a gate that
  fails for a reason you can't explain, anything touching the data boundary or provenance rules.
- **Don't use it** for things the brief, `dev/CONVENTIONS.md`, `dev/GATES.md`, or the code already answer —
  read those first. A request that the docs already answer will just be pointed back at the docs.

## How to raise a request (the mechanism)
1. **Append** a request block to **Open requests** below (use the template). Fill every field; be specific —
   paste the exact error, file:line, and what you already tried.
2. **Commit it** on your feature branch with a normal `Built-By:` commit (the help entry rides along).
3. **Signal it** so it's actually seen — pick the lightest that fits:
   - If you already have a PR open: also drop the same question as a PR comment (fastest — the approver is
     looking there).
   - If you're blocked before a PR: tell your human operator "I posted a HELP request for the lead" so they
     can relay to Rohan. (Humans are the relay when there's no PR yet.)
4. **Keep working** on anything not blocked by the question; don't spin.

## How the lead answers
- Edit the request's **Answer** field in place, commit (`Built-By: rohan`), and move the block to **Resolved**
  once the asker confirms (or once it's clearly addressed). Answer on the PR too if that's where it came from.

## Request template
```
### [OPEN] <short title>  ·  from: <handle>  ·  date: <YYYY-MM-DD>  ·  branch: <handle>/<slug>
**Blocking?** yes/no
**Context:** what you're doing (task id + brief link).
**Question:** the specific thing you need decided/explained.
**What I tried / read:** docs consulted, code inspected, the exact error (file:line / paste).
**My current best guess:** what you'd do if you had to choose (so the lead can just confirm/redirect).
**Answer (lead fills):** —
```

---

## Open requests
_None._

---

## Resolved

### [RESOLVED] Pre-existing cross-platform test failures (UTF-8 + hardcoded clone name)  ·  from: hayes  ·  date: 2026-06-23  ·  branch: hayes/gnomad-constraint
**Question:** harden the 3 pre-existing cross-platform Gate-1 failures in-repo, or treat "run on macOS / set the env" as the expected setup? (moat clone-name test; `test_scenarios`/`test_trace_view` UTF-8 assumptions.)
**Answer (rohan):** Good catch and exactly the right process — you verified pre-existing on clean `main`, scoped them out, and proposed a low-risk fix. Decision: **yes, harden in-repo** — a UTF-8 codebase should not silently fail on a Windows contributor, and the moat test shouldn't depend on the clone directory's name. But **not your job and not in your PR**: I've logged it as the **`crossplatform-test-hardening`** backlog task (status/WORKBOARD.md, suggested rohan/gavin) with your proposed fix (derive the moat suffix from the repo root; add `encoding="utf-8"` to the file read; guard the `✓` stdout write). **Don't let it block you** — keep building on the canonical `sapphire-capability-map` clone with `PYTHONUTF8=1` and proceed to GTEx (PR-B). Thanks for flagging it cleanly rather than papering over it.
