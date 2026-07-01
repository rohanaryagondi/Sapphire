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

from report import synthesize_report, _PROV_TO_LABEL, _build_prompt


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


class TestReportLabels(unittest.TestCase):
    """Item 1: moat → 'Quiver data' in all user-facing provenance labels."""

    def test_moat_real_maps_to_quiver_data(self):
        self.assertEqual(_PROV_TO_LABEL["moat-real"], "Quiver data")

    def test_moat_maps_to_quiver_data(self):
        self.assertEqual(_PROV_TO_LABEL["moat"], "Quiver data")

    def test_internal_maps_to_quiver_data(self):
        self.assertEqual(_PROV_TO_LABEL["internal"], "Quiver data")

    def test_no_internal_moat_string_in_label_map(self):
        self.assertNotIn("Internal moat", _PROV_TO_LABEL.values(),
                         "'Internal moat' must not appear as a value in _PROV_TO_LABEL")

    def test_prompt_uses_quiver_data_not_internal_moat(self):
        prompt = _build_prompt(
            query=_QUERY, dossier=_DOSSIER, round1=_ROUND1, round2=_ROUND2,
            recommendation=_RECOMMENDATION, confidence=_CONFIDENCE,
            known_unknowns=_KNOWN_UNKNOWNS,
        )
        self.assertNotIn("Internal moat", prompt,
                         "Prompt must not contain 'Internal moat'")
        self.assertIn("Quiver data", prompt,
                      "Prompt must reference 'Quiver data'")


class TestReportCitationInstruction(unittest.TestCase):
    """Item 4: single-source paragraph gets ONE citation at the end."""

    def test_single_source_paragraph_rule_in_prompt(self):
        prompt = _build_prompt(
            query=_QUERY, dossier=_DOSSIER, round1=_ROUND1, round2=_ROUND2,
            recommendation=_RECOMMENDATION, confidence=_CONFIDENCE,
            known_unknowns=_KNOWN_UNKNOWNS,
        )
        # The updated instruction must mention per-paragraph single-cite rule
        self.assertIn("ENTIRE paragraph", prompt,
                      "Prompt must include the per-paragraph single-cite rule")
        self.assertIn("do NOT repeat", prompt,
                      "Prompt must say not to repeat the same source token")

    def test_table_instruction_in_prompt(self):
        """Item 5: prompt must tell Claude to produce tables when tabular."""
        prompt = _build_prompt(
            query=_QUERY, dossier=_DOSSIER, round1=_ROUND1, round2=_ROUND2,
            recommendation=_RECOMMENDATION, confidence=_CONFIDENCE,
            known_unknowns=_KNOWN_UNKNOWNS,
        )
        self.assertIn("GitHub-flavored Markdown table", prompt,
                      "Prompt must instruct Claude to use GFM tables when tabular")


class TestReportModelMeta(unittest.TestCase):
    """Item 2: _model_for_contract returns honest labels per kind."""

    def test_emet_playwright_kind(self):
        from harness.runtime import _model_for_contract
        from harness.contracts import Contract

        c = Contract(id="emet-runner", role="", kind="emet-playwright")
        self.assertEqual(_model_for_contract(c), "EMET / BenchSci")

    def test_python_kind(self):
        from harness.runtime import _model_for_contract
        from harness.contracts import Contract

        c = Contract(id="internal-science-lead", role="", kind="python")
        self.assertEqual(_model_for_contract(c), "Quiver data (CNS_DFP)")

    def test_qmodels_kind(self):
        from harness.runtime import _model_for_contract
        from harness.contracts import Contract

        c = Contract(id="q-models-runner", role="", kind="qmodels-delegate")
        self.assertEqual(_model_for_contract(c), "Q-Models launchpad")

    def test_claude_simulated_when_simulate_on(self):
        import os
        from harness.runtime import _model_for_contract
        from harness.contracts import Contract

        c = Contract(id="emet-analyst", role="", kind="claude-subagent")
        os.environ["SAPPHIRE_SIMULATE_MODELS"] = "1"
        try:
            result = _model_for_contract(c)
            self.assertEqual(result, "simulated")
        finally:
            os.environ.pop("SAPPHIRE_SIMULATE_MODELS", None)

    def test_claude_uses_model_env(self):
        import os
        from harness.runtime import _model_for_contract
        from harness.contracts import Contract

        c = Contract(id="emet-analyst", role="", kind="claude-subagent")
        os.environ.pop("SAPPHIRE_SIMULATE_MODELS", None)
        os.environ["CLAUDE_MODEL"] = "claude-haiku-4-5"
        try:
            result = _model_for_contract(c)
            self.assertEqual(result, "claude-haiku-4-5")
        finally:
            os.environ.pop("CLAUDE_MODEL", None)


if __name__ == "__main__":
    unittest.main()
