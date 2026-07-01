"""
Tests for followup.py — main-chat follow-up over a run's stored evidence.

All tests pass with CLAUDE_BIN=/usr/bin/false (no live claude call).
"""
import json
import os
import sys
import unittest

# Ensure sapphire-orchestrator is on the path
_ORCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ORCH_DIR not in sys.path:
    sys.path.insert(0, _ORCH_DIR)

from followup import answer_followup


# ── test helpers ─────────────────────────────────────────────────────────────

class _FakeProc:
    def __init__(self, stdout: str = "", returncode: int = 1):
        self.stdout = stdout
        self.returncode = returncode


def _false_runner(cmd):
    """Mimics /usr/bin/false: returncode=1, empty stdout."""
    return _FakeProc(stdout="", returncode=1)


def _ok_runner(payload: dict):
    """Returns a runner that yields returncode=0 and the given JSON payload."""
    def run(cmd):
        return _FakeProc(stdout=json.dumps(payload), returncode=0)
    return run


def _raw_text_runner(text: str):
    """Returns a runner that yields returncode=0 and raw (non-JSON) text."""
    def run(cmd):
        return _FakeProc(stdout=text, returncode=0)
    return run


def _raising_runner(cmd):
    """Always raises RuntimeError."""
    raise RuntimeError("simulated subprocess failure")


# ── sample data ───────────────────────────────────────────────────────────────

_QUERY = "Is TSC2 a viable target in tuberous sclerosis complex?"
_DOSSIER = [
    {"value": "TSC2 loss activates mTORC1 signaling.", "source": "EMET-PMID:1234", "tier": "T1", "provenance": "emet"},
    {"value": "Internal EP distance TSC2 -> rapamycin: 0.12.", "source": "CNS_DFP", "tier": "T1", "provenance": "moat-real"},
]
_ROUND1 = [
    {"persona": "ex-FDA Regulator", "stance": "conditional", "rationale": "Needs PK data.", "conviction": 3, "status": "ok"},
]
_ROUND2 = [
    {"persona": "ex-FDA Regulator", "stance": "pass", "rationale": "PK data provided.", "conviction": 4, "revised": True, "status": "ok"},
]
_KNOWN_UNKNOWNS = ["Blood-brain-barrier penetrance of lead compound unknown."]

_RESULT = {
    "query": _QUERY,
    "discover": {
        "dossier": _DOSSIER,
        "flags": {"KNOWN_UNKNOWNS": _KNOWN_UNKNOWNS},
    },
    "consult": {"round1": _ROUND1, "round2": _ROUND2},
    "synthesize": {
        "recommendation": "TSC2 is a high-confidence target.",
        "confidence": "high",
    },
}

_EMPTY_RESULT: dict = {}


# ── tests ─────────────────────────────────────────────────────────────────────

class TestFollowupInEvidence(unittest.TestCase):
    """(a) An in-evidence question: answer references dossier content, citations non-empty."""

    def test_in_evidence_answer_and_citations(self):
        payload = {
            "answer": "TSC2 loss activates mTORC1 signaling. [[EMET]]",
            "needs_new_data": False,
            "missing_agent": None,
        }
        out = answer_followup(
            "What does the dossier say about TSC2 and mTORC1?",
            _RESULT,
            runner=_ok_runner(payload),
        )
        self.assertIn("mTORC1", out["answer"])
        self.assertFalse(out["needs_new_data"])
        self.assertIsNone(out["missing_agent"])
        self.assertTrue(out["citations"], "citations must be non-empty when dossier has facts")
        self.assertIn("EMET", out["citations"])
        self.assertIn("Quiver data", out["citations"])


class TestFollowupOutOfEvidence(unittest.TestCase):
    """(b) An out-of-evidence question: needs_new_data=True with a non-null missing_agent,
    and the answer does not fabricate specifics."""

    def test_out_of_evidence_flags_needs_new_data(self):
        payload = {
            "answer": "This run's evidence does not cover binding affinity for this compound.",
            "needs_new_data": True,
            "missing_agent": "a Q-Models binding-affinity run",
        }
        out = answer_followup(
            "What is the binding affinity of compound X to target Y?",
            _RESULT,
            runner=_ok_runner(payload),
        )
        self.assertTrue(out["needs_new_data"])
        self.assertIsNotNone(out["missing_agent"])
        self.assertIn("Q-Models", out["missing_agent"])
        self.assertNotIn("nM", out["answer"], "must not fabricate a specific binding number")


class TestFollowupMalformedJSON(unittest.TestCase):
    """(c) Malformed JSON from the model: falls back to raw text as answer, never raises."""

    def test_malformed_json_falls_back_to_raw_text(self):
        raw = "This is not valid JSON at all -- just prose."
        out = answer_followup("Any question", _RESULT, runner=_raw_text_runner(raw))
        self.assertEqual(out["answer"], raw)
        self.assertFalse(out["needs_new_data"])
        self.assertIsNone(out["missing_agent"])

    def test_json_array_not_object_falls_back(self):
        """A JSON value that parses but isn't an object must still fall back to raw text."""
        raw = '["not", "an", "object"]'
        out = answer_followup("Any question", _RESULT, runner=_raw_text_runner(raw))
        self.assertEqual(out["answer"], raw)
        self.assertFalse(out["needs_new_data"])

    def test_missing_answer_field_falls_back(self):
        """Valid JSON object but missing/empty 'answer' key falls back to raw text."""
        raw = json.dumps({"needs_new_data": False, "missing_agent": None})
        out = answer_followup("Any question", _RESULT, runner=_raw_text_runner(raw))
        self.assertEqual(out["answer"], raw)


class TestFollowupClaudeUnavailable(unittest.TestCase):
    """(d) CLAUDE_BIN unavailable: deterministic fallback, never raises."""

    def test_false_runner_never_raises_and_is_deterministic(self):
        out1 = answer_followup(_QUERY, _RESULT, runner=_false_runner)
        out2 = answer_followup(_QUERY, _RESULT, runner=_false_runner)
        self.assertEqual(out1, out2, "Fallback must be deterministic across two calls.")
        self.assertFalse(out1["needs_new_data"])
        self.assertIsNone(out1["missing_agent"])
        self.assertEqual(out1["citations"], [])
        self.assertIn("Could not reach the model", out1["answer"])

    def test_raising_runner_never_raises(self):
        result = answer_followup(_QUERY, _RESULT, runner=_raising_runner)
        self.assertIsInstance(result, dict)
        self.assertTrue(result["answer"].strip())

    def test_no_real_claude_when_false_bin(self):
        orig = os.environ.get("CLAUDE_BIN")
        try:
            os.environ["CLAUDE_BIN"] = "/usr/bin/false"
            out = answer_followup(_QUERY, _RESULT, runner=_false_runner)
            self.assertIsInstance(out, dict)
            self.assertTrue(out["answer"].strip())
        finally:
            if orig is None:
                os.environ.pop("CLAUDE_BIN", None)
            else:
                os.environ["CLAUDE_BIN"] = orig

    def test_claude_bin_unresolvable_uses_fallback_without_runner(self):
        """When runner=None and CLAUDE_BIN points at a nonexistent binary, shutil.which
        fails and the deterministic fallback is used (no subprocess spawned)."""
        orig = os.environ.get("CLAUDE_BIN")
        try:
            os.environ["CLAUDE_BIN"] = "/definitely/not/a/real/binary/path/claude"
            import importlib
            import followup as _followup_mod
            importlib.reload(_followup_mod)
            out = _followup_mod.answer_followup(_QUERY, _RESULT, runner=None)
            self.assertIsInstance(out, dict)
            self.assertIn("Could not reach the model", out["answer"])
        finally:
            if orig is None:
                os.environ.pop("CLAUDE_BIN", None)
            else:
                os.environ["CLAUDE_BIN"] = orig
            import importlib
            import followup as _followup_mod
            importlib.reload(_followup_mod)


class TestFollowupEmptyResult(unittest.TestCase):
    """(e) Empty dossier/empty result: honest fallback, never crashes."""

    def test_empty_result_dict(self):
        out = answer_followup("What's the mechanism?", _EMPTY_RESULT, runner=_false_runner)
        self.assertIsInstance(out, dict)
        self.assertTrue(out["answer"].strip())
        self.assertEqual(out["citations"], [])
        self.assertFalse(out["needs_new_data"])

    def test_none_result(self):
        out = answer_followup("What's the mechanism?", None, runner=_false_runner)
        self.assertIsInstance(out, dict)
        self.assertTrue(out["answer"].strip())

    def test_empty_dossier_still_returns_dict(self):
        result = {
            "query": "q",
            "discover": {"dossier": [], "flags": {}},
            "consult": {"round1": [], "round2": []},
            "synthesize": {"recommendation": "", "confidence": ""},
        }
        out = answer_followup("Anything?", result, runner=_false_runner)
        self.assertIsInstance(out, dict)
        self.assertTrue(out["answer"].strip())

    def test_empty_question_still_returns_dict(self):
        out = answer_followup("", _RESULT, runner=_ok_runner(
            {"answer": "N/A", "needs_new_data": False, "missing_agent": None}
        ))
        self.assertIsInstance(out, dict)
        self.assertTrue(out["answer"].strip())


class TestFollowupReturnShape(unittest.TestCase):
    """The return dict always has exactly the contracted keys."""

    def test_return_keys(self):
        out = answer_followup(_QUERY, _RESULT, runner=_false_runner)
        for key in ("answer", "citations", "needs_new_data", "missing_agent"):
            self.assertIn(key, out)


if __name__ == "__main__":
    unittest.main()
