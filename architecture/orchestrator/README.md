# Orchestrator — the control layer

The three agents that run the firm: they don't gather facts or render verdicts themselves — they
**plan the work, decide when the facts are complete, and run the debate.** Together they own the
Bucket-1 ↔ Bucket-2 loop and write the final report.

### [Engagement Lead](engagement-lead.md)
The firm's front door (entry point for every prompt). Interprets the question, scopes which
[dossier](../../sapphire-orchestrator/dossier_schema.md) fields are *required* vs *skip*, and writes
the engagement plan — the minimal set of agents to activate and the provisional partner panel. Owns
the loop end to end and delivers the report; never forces consensus.

### [Research Manager](research-manager.md)
Owns Bucket 1. Slots every returned claim into its dossier field with source / credibility tier /
confidence, checks each required field is filled to the bar, resolves contradictions toward the higher
tier, and surfaces **VETO** gates and internal↔external **DIVERGENCE** (without reconciling it). Orders
*targeted* re-runs until the dossier is complete or the round/budget cap hits.

### [Roundtable Moderator](roundtable-moderator.md)
Owns Bucket 2. Seats 3–7 partners (one per relevant lens, disease-matched, **always** the Red-Team),
runs Round 1 independent verdicts then a Round 2 moderated rebuttal, routes any partner fact-request
back to Bucket 1, and maps the spread — consensus, genuine disagreement and *why*, the convergent gate.
