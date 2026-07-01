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
            "answer": "TSC2 loss activates mTORC1 signaling. [[EMET]] Internal EP distance data agrees. [[Quiver data]]",
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
        # citations reflect only the [[tokens]] actually present in the answer —
        # this payload cites both, so both should appear.
        self.assertTrue(out["citations"], "citations must be non-empty when the answer cites evidence")
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

    def test_missing_answer_field_never_dumps_raw_json(self):
        """Valid JSON object but missing/empty 'answer' key must NEVER dump the raw
        JSON braces to the user — degrade to a generic honest message instead."""
        raw = json.dumps({"needs_new_data": False, "missing_agent": None})
        out = answer_followup("Any question", _RESULT, runner=_raw_text_runner(raw))
        self.assertNotEqual(out["answer"], raw)
        self.assertNotIn("{", out["answer"])
        self.assertTrue(out["answer"].strip())


class TestFollowupRealStyleOutput(unittest.TestCase):
    """Real Claude output is rarely clean JSON — fenced blocks, a preamble, trailing
    prose, or an unescaped char are all common. These regressions guard the exact bug
    Gate-5 caught on a live /api/followup call: the strict json.loads path threw and
    the except branch dumped the raw JSON string to the UI instead of prose."""

    def test_fenced_json_parses_cleanly(self):
        """```json fences``` around an otherwise-valid object must not break parsing,
        and the fence markers must never leak into the rendered answer."""
        payload = {
            "answer": "TSC2 loss drives mTORC1 hyperactivation. [[EMET]]",
            "needs_new_data": False,
            "missing_agent": None,
        }
        raw = "```json\n" + json.dumps(payload) + "\n```"
        out = answer_followup("What about TSC2 and mTORC1?", _RESULT, runner=_raw_text_runner(raw))
        self.assertEqual(out["answer"], payload["answer"])
        self.assertNotIn("```", out["answer"])
        self.assertFalse(out["needs_new_data"])

    def test_json_with_preamble_and_trailing_prose_parses(self):
        """A short preamble before the object and trailing prose after it (both common
        in real model output despite an explicit 'no preamble' instruction) must not
        break extraction — the balanced-object scan finds the object regardless."""
        payload = {
            "answer": "Internal EP distance data supports this target. [[Quiver data]]",
            "needs_new_data": False,
            "missing_agent": None,
        }
        raw = (
            "Here's the answer based on the evidence:\n\n"
            + json.dumps(payload)
            + "\n\nLet me know if you need more detail."
        )
        out = answer_followup("Any internal support?", _RESULT, runner=_raw_text_runner(raw))
        self.assertEqual(out["answer"], payload["answer"])
        self.assertNotIn("Here's the answer", out["answer"])
        self.assertNotIn("Let me know", out["answer"])

    def test_bare_prose_with_no_json_structure_renders_as_answer(self):
        """A model that ignores the JSON instruction entirely and just answers in
        plain prose is still a valid, honest answer — render it as-is."""
        raw = "Based on the dossier, TSC2 loss activates mTORC1 signaling."
        out = answer_followup("What about TSC2?", _RESULT, runner=_raw_text_runner(raw))
        self.assertEqual(out["answer"], raw)
        self.assertFalse(out["needs_new_data"])
        self.assertIsNone(out["missing_agent"])

    def test_unescaped_control_char_still_recovers_full_object(self):
        """A raw (unescaped) newline inside the answer string breaks strict()
        json.loads (JSON strings must escape control characters) but must still
        recover the full answer/needs_new_data/missing_agent object — never fall
        back to dumping the raw broken-JSON blob."""
        raw = '{"answer": "Line one.\nLine two.", "needs_new_data": false, "missing_agent": null}'
        out = answer_followup("Any question", _RESULT, runner=_raw_text_runner(raw))
        self.assertIn("Line one", out["answer"])
        self.assertNotIn('"needs_new_data"', out["answer"])
        self.assertFalse(out["needs_new_data"])
        self.assertIsNone(out["missing_agent"])

    def test_citations_reflect_only_tokens_actually_used_in_answer(self):
        """citations must reflect the [[tokens]] actually present in the final answer,
        not every label that was available as context in the dossier."""
        payload = {
            # Dossier has both EMET and Quiver-data facts (see _RESULT), but this
            # answer only cites Quiver data.
            "answer": "Internal EP distance data supports this target. [[Quiver data]]",
            "needs_new_data": False,
            "missing_agent": None,
        }
        out = answer_followup("Any internal support?", _RESULT, runner=_ok_runner(payload))
        self.assertIn("Quiver data", out["citations"])
        self.assertNotIn("EMET", out["citations"], "must not claim a citation the answer never used")

    def test_citations_empty_when_answer_cites_nothing(self):
        payload = {"answer": "No relevant evidence in this run.", "needs_new_data": False, "missing_agent": None}
        out = answer_followup("Anything on X?", _RESULT, runner=_ok_runner(payload))
        self.assertEqual(out["citations"], [])


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
