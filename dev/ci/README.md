# CI templates (staged — not active)

`branch-guard.yml` is the **detective backstop** for the branch rules (fails bad PR branch names; files an
issue on a direct push to `main`). It is parked here, **not** under `.github/workflows/`, because GitHub
Actions does not run on this free-tier private repo today — jobs fail at runner allocation (no steps, ~4s),
the free-tier private-Actions billing/minutes signature. A workflow left active there would red-X every PR and
block merges, so it's staged here instead.

## Activate it (when the repo has working Actions)
This unlocks together with server-side branch protection — i.e. once `rohanaryagondi` is on **GitHub Pro**
(and Actions minutes/billing are available for private repos):
```
git mv dev/ci/branch-guard.yml .github/workflows/branch-guard.yml
# commit on a feature branch + PR as usual; confirm a run actually executes steps.
bash dev/enable-branch-protection.sh   # the server-side preventive layer
```

## Until then
Enforcement is the **client-side git hooks** (`.githooks/`, installed by `dev/setup-contributor.sh`) plus
CODEOWNERS review-routing and `dev/CONTRIBUTOR_RULES.md`. The hooks are the real, verified free-tier guard;
this workflow is the server-side belt-and-suspenders for later.
