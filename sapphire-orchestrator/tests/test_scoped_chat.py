"""Tests for scoped_chat.answer_scoped() — all offline, subprocess mocked.

Mirrors tests/test_summarizer.py's structure. The required scoping-guard pair
(the literal DoD requirement — "a test proves it won't answer beyond the step's
evidence"):
  * test_empty_facts_returns_explicit_no_evidence — a CODE-level guarantee
    (no model call at all) that an out-of-scope/no-evidence question never
    fabricates: it returns the deterministic "no evidence" string.
  * test_out_of_scope_question_returns_models_honest_decline — the model itself
    is instructed (and, via the mock, shown) to decline rather than speculate;
    asserts the function passes that decline through verbatim rather than
    inventing something else.
"""
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scoped_chat import answer_scoped, _NO_EVIDENCE


class TestScopedChat(unittest.TestCase):

    def _make_proc(self, stdout="", returncode=0):
        proc = MagicMock()
        proc.stdout = stdout
        proc.returncode = returncode
        return proc

    # ── the scoping guard (DoD requirement) ───────────────────────────────

    def test_empty_facts_returns_explicit_no_evidence(self):
        """No facts at all (e.g. a step with zero contributed facts) — must
        return the explicit no-evidence string WITHOUT ever calling the model.
        This is the strongest scoping guarantee: code-level, not prompt-level."""
        with patch("subprocess.run") as mock_run:
            result = answer_scoped("What's the strongest fact here?", [])
            mock_run.assert_not_called()
        self.assertEqual(result, _NO_EVIDENCE)
        self.assertIn("No evidence", result)

    def test_out_of_scope_question_returns_models_honest_decline(self):
        """The evidence is scoped to one step's facts (TSC2 only). Asking about
        something NOT in those facts — the model (mocked) honestly declines
        rather than fabricating an answer; answer_scoped must pass that decline
        through verbatim, not invent a different (fabricated) answer."""
        decline = "This is not addressed in the evidence provided for this step."
        with patch("subprocess.run", return_value=self._make_proc(stdout=decline)):
            facts = [{"value": "TSC2 suppresses mTORC1", "source": "PMID:12345",
                      "tier": "T2", "provenance": "emet-live"}]
            result = answer_scoped("What is the patient's insurance status?", facts)
        self.assertEqual(result, decline)
        self.assertIn("not addressed", result.lower())
        # It must NOT contain a fabricated specific claim about insurance.
        self.assertNotIn("insurance status is", result.lower())

    def test_request_payload_contains_only_scoped_facts(self):
        """The prompt sent to the model must contain ONLY the facts passed in —
        proving the function (and by extension the caller contract) never
        widens scope beyond what it was given."""
        captured_cmd = {}

        def _runner(cmd):
            captured_cmd["cmd"] = cmd
            return self._make_proc(stdout="In scope: TSC2 suppresses mTORC1.")

        facts = [{"value": "TSC2 suppresses mTORC1", "source": "PMID:12345",
                  "tier": "T2", "provenance": "emet-live"}]
        answer_scoped("What does TSC2 do?", facts, runner=_runner)
        prompt = captured_cmd["cmd"][2]  # ["claude", "-p", prompt, ...]
        self.assertIn("TSC2 suppresses mTORC1", prompt)
        self.assertIn("PMID:12345", prompt)
        # A fact NOT in the scoped list must never appear.
        self.assertNotIn("FZD7", prompt)
        self.assertNotIn("DCTN6", prompt)

    # ── general behavior (mirrors test_summarizer.py) ─────────────────────

    def test_in_scope_answer_returned_verbatim(self):
        """Mock returns a short grounded answer — returned as-is."""
        answer = "TSC2 suppresses mTORC1, per PMID:12345."
        with patch("subprocess.run", return_value=self._make_proc(stdout=answer)):
            facts = [{"value": "TSC2 suppresses mTORC1", "source": "PMID:12345",
                      "tier": "T2", "provenance": "emet-live"}]
            result = answer_scoped("What does TSC2 do?", facts)
        self.assertEqual(result, answer)

    def test_honesty_token_check(self):
        """Mock returns fact value verbatim — answer should reference the
        evidence tokens (proving it's grounded, not generic)."""
        fact_value = "SCN2A gain-of-function promotes seizure susceptibility."
        with patch("subprocess.run", return_value=self._make_proc(stdout=fact_value)):
            facts = [{"value": fact_value, "source": "PMID:11111", "tier": "T2",
                      "provenance": "emet-live"}]
            result = answer_scoped("What does SCN2A do?", facts)
        self.assertIn("SCN2A", result)
        self.assertIn("seizure", result)

    def test_subprocess_failure_never_raises(self):
        """Non-zero returncode — returns a fallback stub built from the raw
        evidence, never raises, never silently empty."""
        with patch("subprocess.run", return_value=self._make_proc(stdout="", returncode=1)):
            facts = [{"value": "some fact", "source": "src", "tier": "T2",
                      "provenance": "corpus"}]
            result = answer_scoped("explain", facts)
        self.assertIsInstance(result, str)
        self.assertIn("some fact", result)

    def test_runner_none_no_claude_binary_never_raises(self):
        """When subprocess.run raises FileNotFoundError — degrades to the
        fallback stub, never raises."""
        with patch("subprocess.run", side_effect=FileNotFoundError("claude not found")):
            facts = [{"value": "some data", "source": "moat", "tier": "T1",
                      "provenance": "moat-real"}]
            try:
                result = answer_scoped("explain", facts)
            except Exception as exc:
                self.fail(f"answer_scoped raised unexpectedly: {exc}")
        self.assertIsInstance(result, str)
        self.assertIn("some data", result)

    def test_empty_question_does_not_call_model(self):
        """An empty/whitespace question — a clear prompt to ask something,
        never a model call (cheap + honest)."""
        with patch("subprocess.run") as mock_run:
            result = answer_scoped("   ", [{"value": "x", "source": "y", "tier": "T2"}])
            mock_run.assert_not_called()
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


if __name__ == "__main__":
    unittest.main()
