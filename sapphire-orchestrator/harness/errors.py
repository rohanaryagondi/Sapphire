"""Harness error taxonomy + fail-safe envelopes (spec §A.7). A failure becomes
an honest abstain/escalate the orchestrator already slots — never a fabricated fact."""
from __future__ import annotations

HARNESS_ERRORS = frozenset({
    "malformed-output", "guardrail-violation", "timeout",
    "tool-failure", "login-required", "budget", "unknown-agent",
})


class HarnessEscalation(Exception):
    """Raised/returned when a run must pause for a human (e.g. EMET login). Never swallowed."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def abstain_envelope(code: str, would_need: str) -> dict:
    return {"abstained": True, "reason": code, "would_need": would_need}


def escalate(code: str, detail: str = "") -> HarnessEscalation:
    return HarnessEscalation(code, detail)
