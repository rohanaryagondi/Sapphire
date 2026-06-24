"""Sapphire Experiment Design tool (Phase 1, ED-1).

Standalone Quiver tool: an Otter meeting transcript -> a structured experiment
design plan (JSON + Markdown), via Claude. Ported from Matt Carey's
design-form-agent (see README.md + vendor/design-form-agent/VENDORED.md); the
domain prompt / MENUS_REFERENCE / schema are preserved verbatim.

Standalone: NOT imported by the Sapphire engine (which stays stdlib-only) — the
`anthropic` dep lives in this tool's subprocess. Data boundary: transcripts go
only to the LLM + local files, never to an external evidence source.
"""
