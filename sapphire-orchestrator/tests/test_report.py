"""
Tests for report.py — the full-narrative diligence report synthesizer.

All tests pass with CLAUDE_BIN=/usr/bin/false (no live claude call).
"""
import os
import sys
import unittest

# Ensure sapphire-orchestrator is on the path
_ORCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ORCH_DIR not in sys.path:
    sys.path.insert(0, _ORCH_DIR)

from report import synthesize_report


# ── test helpers ─────────────────────────────────────────────────────────────

class _FakeProc:
    def __init__(self, stdout: str = "", returncode: int = 1):
        self.stdout = stdout
        self.returncode = returncode


def _false_runner(cmd):
    """Mimics /usr/bin/false: returncode=1, empty stdout."""
    return _FakeProc(stdout="", returncode=1)


def _ok_runner(text: str):
    """Returns a runner that yields returncode=0 and the given text."""
    def run(cmd):
        return _FakeProc(stdout=text, returncode=0)
    return run


def _raising_runner(cmd):
    """Always raises RuntimeError."""
    raise RuntimeError("simulated subprocess failure")


# ── sample data ───────────────────────────────────────────────────────────────

_QUERY = "Is TSC2 a viable target in tuberous sclerosis complex?"
_RECOMMENDATION = "TSC2 is a high-confidence target; mTORC1 inhibition with a blood-brain-barrier-penetrant compound warrants clinical investigation."
_CONFIDENCE = "high"
_DOSSIER = [
    {"value": "TSC2 loss activates mTORC1 signaling.", "source": "EMET-PMID:1234", "tier": "T1", "provenance": "emet"},
    {"value": "Internal EP distance TSC2 → rapamycin: 0.12.", "source": "CNS_DFP", "tier": "T1", "provenance": "moat-real"},
]
_ROUND1 = [
    {"persona": "ex-FDA Regulator", "stance": "conditional", "rationale": "Needs PK data.", "conviction": 3, "status": "ok"},
]
_ROUND2 = [
    {"persona": "ex-FDA Regulator", "stance": "pass", "rationale": "PK data provided.", "conviction": 4, "revised": True, "status": "ok"},
]
_KNOWN_UNKNOWNS = ["Blood-brain-barrier penetrance of lead compound unknown.", "Long-term safety data not yet available."]


# ── tests ─────────────────────────────────────────────────────────────────────

class TestReportFallback(unittest.TestCase):

    def test_fallback_is_deterministic(self):
        """Calling with a failing runner twice must return identical strings."""
        out1 = synthesize_report(
            query=_QUERY, dossier=_DOSSIER, round1=_ROUND1, round2=_ROUND2,
            recommendation=_RECOMMENDATION, confidence=_CONFIDENCE,
            known_unknowns=_KNOWN_UNKNOWNS, runner=_false_runner,
        )
        out2 = synthesize_report(
            query=_QUERY, dossier=_DOSSIER, round1=_ROUND1, round2=_ROUND2,
            recommendation=_RECOMMENDATION, confidence=_CONFIDENCE,
            known_unknowns=_KNOWN_UNKNOWNS, runner=_false_runner,
        )
        self.assertEqual(out1, out2, "Fallback must be deterministic across two calls.")

    def test_fallback_is_nonempty(self):
        """Fallback must return a non-empty string."""
        out = synthesize_report(
            query=_QUERY, dossier=_DOSSIER, round1=_ROUND1, round2=_ROUND2,
            recommendation=_RECOMMENDATION, confidence=_CONFIDENCE,
            known_unknowns=_KNOWN_UNKNOWNS, runner=_false_runner,
        )
        self.assertTrue(out.strip(), "Fallback must not be empty.")

    def test_fallback_contains_recommendation(self):
        """Fallback output must contain the recommendation text."""
        out = synthesize_report(
            query=_QUERY, dossier=_DOSSIER, round1=_ROUND1, round2=_ROUND2,
            recommendation=_RECOMMENDATION, confidence=_CONFIDENCE,
            known_unknowns=_KNOWN_UNKNOWNS, runner=_false_runner,
        )
        self.assertIn(_RECOMMENDATION, out,
                      "Fallback must include the recommendation string.")

    def test_fallback_never_raises(self):
        """A runner that raises RuntimeError must not propagate — returns a string."""
        result = synthesize_report(
            query=_QUERY, dossier=_DOSSIER, round1=_ROUND1, round2=_ROUND2,
            recommendation=_RECOMMENDATION, confidence=_CONFIDENCE,
            known_unknowns=_KNOWN_UNKNOWNS, runner=_raising_runner,
        )
        self.assertIsInstance(result, str, "Must return str even when runner raises.")
        self.assertTrue(result.strip(), "Returned string must not be empty.")

    def test_no_real_claude_when_false_bin(self):
        """When CLAUDE_BIN=/usr/bin/false, no live subprocess succeeds; still returns str."""
        orig = os.environ.get("CLAUDE_BIN")
        try:
            os.environ["CLAUDE_BIN"] = "/usr/bin/false"
            # Import fresh or use the _false_runner to avoid triggering shutil.which path
            out = synthesize_report(
                query=_QUERY, dossier=_DOSSIER, round1=_ROUND1, round2=_ROUND2,
                recommendation=_RECOMMENDATION, confidence=_CONFIDENCE,
                known_unknowns=_KNOWN_UNKNOWNS, runner=_false_runner,
            )
            self.assertIsInstance(out, str)
            self.assertTrue(out.strip())
        finally:
            if orig is None:
                os.environ.pop("CLAUDE_BIN", None)
            else:
                os.environ["CLAUDE_BIN"] = orig

    def test_claude_output_returned(self):
        """When runner returns a valid markdown string, it is returned as-is."""
        expected = "# Sapphire Diligence Report\n\nTSC2 is a high-confidence target."
        out = synthesize_report(
            query=_QUERY, dossier=_DOSSIER, round1=_ROUND1, round2=_ROUND2,
            recommendation=_RECOMMENDATION, confidence=_CONFIDENCE,
            known_unknowns=_KNOWN_UNKNOWNS, runner=_ok_runner(expected),
        )
        self.assertEqual(out, expected, "Claude output must be returned verbatim.")

    def test_empty_inputs(self):
        """Empty dossier, rounds, and known_unknowns must still return non-empty string."""
        out = synthesize_report(
            query="", dossier=[], round1=[], round2=[],
            recommendation="", confidence="",
            known_unknowns=[], runner=_false_runner,
        )
        self.assertIsInstance(out, str)
        self.assertTrue(out.strip(), "Even with empty inputs the fallback must not be empty.")


if __name__ == "__main__":
    unittest.main()
