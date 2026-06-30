"""
test_summarizer.py — unit tests for the per-step summarizer seam.

All tests are offline ($0): the subprocess is mocked so no live claude binary
is needed.  The harness import path is tested via a minimal runner injection.
"""
from __future__ import annotations

import sys
import os
import types
import unittest
from unittest.mock import MagicMock, patch

# Ensure the sapphire-orchestrator package root is on sys.path.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from summarizer import summarize_step, _fallback, _WORD_BUDGET_HARD


class _FakeProc:
    """Minimal subprocess.CompletedProcess mock."""
    def __init__(self, stdout: str = "", returncode: int = 0):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = ""


def _runner(text: str, returncode: int = 0):
    """Return a runner callable that always returns the given text."""
    def run(cmd):
        return _FakeProc(stdout=text, returncode=returncode)
    return run


class TestSummarizerWordBudget(unittest.TestCase):
    """Word budget is respected; outputs within budget pass through."""

    def test_short_summary_returned_as_is(self):
        """A short (≤18-word) response from the model is returned verbatim."""
        facts = [{"value": "TSC2 mutation rate is 0.3%", "source": "PMID123", "provenance": "emet-live"}]
        result = summarize_step(facts, "emet-runner", runner=_runner("TSC2 drives mTORC1 hyperactivation in tuberous sclerosis cells"))
        self.assertEqual(result, "TSC2 drives mTORC1 hyperactivation in tuberous sclerosis cells")

    def test_over_budget_falls_back(self):
        """A 25-word response (over the 20-word hard limit) falls back to the stub."""
        long_text = " ".join(["word"] * 25)  # 25 words — over the hard limit of 20
        facts = [{"value": "TSC2 is implicated", "source": "PMID999", "provenance": "emet-live"}]
        result = summarize_step(facts, "emet-runner", runner=_runner(long_text))
        # Should fall back to "N facts · provenance"
        self.assertIn("1 fact", result)
        self.assertIn("emet-live", result)

    def test_exactly_at_budget_passes(self):
        """Exactly 18-word response passes (at the soft limit)."""
        text_18 = " ".join([f"w{i}" for i in range(18)])
        facts = [{"value": "x", "source": "s", "provenance": "emet-live"}]
        result = summarize_step(facts, "emet-runner", runner=_runner(text_18))
        self.assertEqual(result, text_18)

    def test_at_hard_limit_passes(self):
        """Exactly 20-word response passes (at the hard limit)."""
        text_20 = " ".join([f"w{i}" for i in range(20)])
        facts = [{"value": "x", "source": "s", "provenance": "emet-live"}]
        result = summarize_step(facts, "emet-runner", runner=_runner(text_20))
        self.assertEqual(result, text_20)

    def test_over_hard_limit_by_one_falls_back(self):
        """21-word response (one over hard limit) falls back."""
        text_21 = " ".join([f"w{i}" for i in range(21)])
        facts = [{"value": "x", "source": "s", "provenance": "moat-real"}]
        result = summarize_step(facts, "internal-science-lead", runner=_runner(text_21))
        self.assertIn("1 fact", result)
        self.assertIn("moat-real", result)


class TestSummarizerFailures(unittest.TestCase):
    """Graceful fallback on subprocess failure, timeout, exception."""

    def test_nonzero_exit_falls_back(self):
        """Non-zero exit code from subprocess returns fallback, never raises."""
        facts = [{"value": "drug X inhibits target Y", "source": "PMID1", "provenance": "emet-live"}]
        result = summarize_step(facts, "emet-runner", runner=_runner("", returncode=1))
        self.assertIn("1 fact", result)
        self.assertNotEqual(result, "")

    def test_empty_stdout_falls_back(self):
        """Empty stdout returns fallback."""
        facts = [{"value": "blah", "source": "src", "provenance": "semantic-web"}]
        result = summarize_step(facts, "clinical-trial-registry", runner=_runner(""))
        self.assertIn("1 fact", result)

    def test_runner_raises_falls_back(self):
        """Runner that raises returns fallback, never re-raises."""
        def raising_runner(cmd):
            raise RuntimeError("subprocess timeout")
        facts = [{"value": "some fact", "source": "src", "provenance": "emet-live"}]
        result = summarize_step(facts, "emet-runner", runner=raising_runner)
        # Must not raise; must return a non-empty string
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_empty_facts_returns_valid_string(self):
        """Empty facts list returns a deterministic non-empty fallback, never raises."""
        result = summarize_step([], "fda-institutional-memory", runner=_runner("No cited facts returned by this agent."))
        # The runner response is within budget, so it passes through.
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_empty_facts_fallback_via_failure(self):
        """Empty facts + subprocess failure → fallback string."""
        result = summarize_step([], "fda-institutional-memory", runner=_runner("", returncode=1))
        # Fallback: "0 facts · fda-institutional-memory"
        self.assertIn("0 facts", result)
        self.assertIn("fda-institutional-memory", result)


class TestSummarizerHonestyHeuristic(unittest.TestCase):
    """Heuristic honesty check: a reasonable summary over a fixed fact set
    should contain tokens that appear in the fact text (no hallucination test)."""

    def test_summary_contains_tokens_from_facts(self):
        """When the model echoes fact content, the summary contains those tokens.

        This is a heuristic, not a semantic proof, but it guards against
        completions that bear zero relation to the input evidence.
        """
        facts = [{"value": "TSC2 mutation rate is 0.3% in the population", "source": "PMID123", "provenance": "emet-live"}]
        # Simulate a faithful model response that restates from the fact
        faithful_summary = "TSC2 mutation rate is 0.3% in population studies"
        result = summarize_step(facts, "emet-runner", runner=_runner(faithful_summary))
        # The summary must contain at least one key token from the fact
        tokens_in_fact = {"TSC2", "0.3%", "mutation", "rate"}
        result_tokens = set(result.split())
        self.assertTrue(
            bool(tokens_in_fact & result_tokens),
            f"Summary '{result}' contains none of the expected fact tokens {tokens_in_fact}",
        )


class TestFallbackFunction(unittest.TestCase):
    """Direct tests on the _fallback helper."""

    def test_fallback_with_provenance(self):
        facts = [{"value": "x", "source": "s", "provenance": "moat-real"}]
        self.assertEqual(_fallback(facts, "internal-science-lead"), "1 fact · moat-real")

    def test_fallback_no_provenance_uses_agent_id(self):
        facts = [{"value": "x", "source": "s"}]
        self.assertEqual(_fallback(facts, "emet-runner"), "1 fact · emet-runner")

    def test_fallback_zero_facts(self):
        self.assertEqual(_fallback([], "gnomad-constraint"), "0 facts · gnomad-constraint")

    def test_fallback_plural(self):
        facts = [{"value": "a", "source": "s"}, {"value": "b", "source": "s"}]
        fb = _fallback(facts, "test-agent")
        self.assertIn("2 facts", fb)


if __name__ == "__main__":
    unittest.main()
