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

from followup import answer_followup, _build_prompt, _build_synthesis_blocks, _valid_targets


class _FakeQModelsClient:
    """Hermetic stand-in for qmodels.client.QModelsClient — no network/subprocess."""

    def __init__(self, tools):
        self._tools = tools

    def tools(self):
        return list(self._tools)


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
        # WO-9 Phase 5: missing_agent must now be a REAL, invocable id — "dti" (a real
        # Q-Models tool id) — never free prose. See TestFollowupMissingAgentTargeting
        # below for the full valid-id / hallucinated-id / no-targets matrix.
        payload = {
            "answer": "This run's evidence does not cover binding affinity for this compound.",
            "needs_new_data": True,
            "missing_agent": "dti",
        }
        out = answer_followup(
            "What is the binding affinity of compound X to target Y?",
            _RESULT,
            runner=_ok_runner(payload),
            qmodels_client=_FakeQModelsClient([{"id": "dti", "label": "DTI / Binder Triage"}]),
            registry={"agents": []},
        )
        self.assertTrue(out["needs_new_data"])
        self.assertEqual(out["missing_agent"], "dti")
        self.assertEqual(out["missing_agent_label"], "DTI / Binder Triage")
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
        for key in ("answer", "citations", "needs_new_data", "missing_agent", "missing_agent_label"):
            self.assertIn(key, out)


class TestFollowupMissingAgentTargeting(unittest.TestCase):
    """WO-9 Phase 5 — `missing_agent` is constrained to a real, invocable id (never
    free prose): a closed {id,label} list is built from the registry + Q-Models tool
    list and injected into the prompt; the parsed response is re-validated against
    the SAME list after parsing. All registry/qmodels lookups are mocked (hermetic)."""

    _REGISTRY = {"agents": [
        {"id": "post-market-safety"},
        {"id": "emet-runner"},
    ]}
    _QMODELS = _FakeQModelsClient([
        {"id": "dti", "label": "DTI / Binder Triage"},
        {"id": "kg_hypothesis", "label": None},  # no label -> falls back to id
    ])

    def test_valid_id_response_passes_through(self):
        payload = {
            "answer": "This run has no post-market safety data for this class.",
            "needs_new_data": True,
            "missing_agent": "post-market-safety",
        }
        out = answer_followup(
            "What does the FAERS record show for this class?",
            _RESULT,
            runner=_ok_runner(payload),
            registry=self._REGISTRY,
            qmodels_client=self._QMODELS,
        )
        self.assertEqual(out["missing_agent"], "post-market-safety")
        self.assertEqual(out["missing_agent_label"], "Post-Market Safety")

    def test_valid_qmodels_tool_id_with_no_registry_label_falls_back_to_id(self):
        payload = {
            "answer": "No KG hypothesis data in this run.",
            "needs_new_data": True,
            "missing_agent": "kg_hypothesis",
        }
        out = answer_followup(
            "Any hypothesis generation on this target?",
            _RESULT,
            runner=_ok_runner(payload),
            registry=self._REGISTRY,
            qmodels_client=self._QMODELS,
        )
        self.assertEqual(out["missing_agent"], "kg_hypothesis")
        self.assertEqual(out["missing_agent_label"], "kg_hypothesis")

    def test_hallucinated_id_coerced_to_null(self):
        """A plausible-sounding but FAKE id (not in the closed list) must never reach
        the caller — this is the correctness-critical defensive guard."""
        payload = {
            "answer": "This run's evidence does not cover that.",
            "needs_new_data": True,
            "missing_agent": "toxicology-deep-dive-agent",  # not a real id anywhere
        }
        out = answer_followup(
            "What about deep toxicology?",
            _RESULT,
            runner=_ok_runner(payload),
            registry=self._REGISTRY,
            qmodels_client=self._QMODELS,
        )
        self.assertIsNone(out["missing_agent"])
        self.assertIsNone(out["missing_agent_label"])

    def test_free_prose_missing_agent_coerced_to_null(self):
        """The OLD free-prose contract ("a Q-Models binding-affinity run") must now
        be rejected — it is not an id in the closed list."""
        payload = {
            "answer": "No binding data here.",
            "needs_new_data": True,
            "missing_agent": "a Q-Models binding-affinity run",
        }
        out = answer_followup(
            "Binding affinity?",
            _RESULT,
            runner=_ok_runner(payload),
            registry=self._REGISTRY,
            qmodels_client=self._QMODELS,
        )
        self.assertIsNone(out["missing_agent"])

    def test_null_missing_agent_stays_null(self):
        payload = {"answer": "In evidence.", "needs_new_data": False, "missing_agent": None}
        out = answer_followup(
            "In-evidence question", _RESULT, runner=_ok_runner(payload),
            registry=self._REGISTRY, qmodels_client=self._QMODELS,
        )
        self.assertIsNone(out["missing_agent"])
        self.assertIsNone(out["missing_agent_label"])

    def test_prompt_includes_the_id_list(self):
        """The built prompt string actually contains the valid target ids/labels —
        a unit test on _build_prompt directly, mocking registry/qmodels lookups."""
        targets = _valid_targets(registry=self._REGISTRY, qmodels_client=self._QMODELS)
        prompt = _build_prompt("Any question?", _RESULT, citation_labels=[], valid_targets=targets)
        self.assertIn("post-market-safety", prompt)
        self.assertIn("Post-Market Safety", prompt)
        self.assertIn("emet-runner", prompt)
        self.assertIn("dti", prompt)
        self.assertIn("DTI / Binder Triage", prompt)
        self.assertIn("NEVER free", prompt)

    def test_no_valid_targets_instructs_always_null(self):
        """When the registry/qmodels lookups both come back empty (offline/degraded),
        the prompt honestly instructs the model that missing_agent must always be null
        rather than presenting an empty-but-implied list."""
        prompt = _build_prompt("Any question?", _RESULT, citation_labels=[], valid_targets=[])
        self.assertIn("MUST be null", prompt)


class TestFollowupSynthesisContext(unittest.TestCase):
    """WO-9 — follow-up sees the final report + ranking.

    (a) A result WITH synthesize.ranked_genes + report → the built prompt contains
        the ranking + report text (so ranking/report questions are answerable).
    (b) "Show me the full ranking" answerable from synthesis → NOT marked needs_new_data.
    (c) Empty first response → retried once; the retry's good response is returned.
    (d) Result without a synthesize block → no crash (backward-compatible).
    """

    _RANKED_GENES = [
        {"gene": "TSC2", "score": 0.95, "rationale": "mTORC1 hyperactivation driver"},
        {"gene": "MTOR", "score": 0.88, "rationale": "Direct downstream effector"},
        {"gene": "RHEB", "score": 0.81},
    ]
    _REPORT_TEXT = (
        "## Synthesis Report\n\n"
        "TSC2 is ranked #1 with score 0.95. MTOR is #2. "
        "The roundtable reached a conditional-pass for TSC2 based on mTORC1 evidence."
    )

    _RESULT_WITH_SYNTHESIS = {
        "query": _QUERY,
        "discover": {
            "dossier": _DOSSIER,
            "flags": {"KNOWN_UNKNOWNS": _KNOWN_UNKNOWNS},
        },
        "consult": {"round1": _ROUND1, "round2": _ROUND2},
        "synthesize": {
            "recommendation": "TSC2 is a high-confidence target.",
            "confidence": "high",
            "ranked_genes": _RANKED_GENES,
            "report": _REPORT_TEXT,
        },
    }

    def test_prompt_contains_ranking_and_report(self):
        """(a) With synthesize.ranked_genes + report → prompt contains FINAL RANKING and
        FINAL REPORT blocks with actual content, so the model can answer ranking questions."""
        prompt = _build_prompt(
            "Show me the full ranking",
            self._RESULT_WITH_SYNTHESIS,
            citation_labels=[],
        )
        self.assertIn("FINAL RANKING", prompt)
        self.assertIn("TSC2", prompt)
        self.assertIn("MTOR", prompt)
        self.assertIn("FINAL REPORT", prompt)
        self.assertIn("Synthesis Report", prompt)
        self.assertIn("0.95", prompt)

    def test_build_synthesis_blocks_ranked_genes_and_report(self):
        """_build_synthesis_blocks renders ranked_genes compactly and includes report text."""
        block = _build_synthesis_blocks(self._RESULT_WITH_SYNTHESIS["synthesize"])
        self.assertIn("FINAL RANKING", block)
        self.assertIn("1. TSC2", block)
        self.assertIn("score: 0.95", block)
        self.assertIn("mTORC1 hyperactivation driver", block)
        self.assertIn("2. MTOR", block)
        self.assertIn("FINAL REPORT", block)
        self.assertIn("Synthesis Report", block)

    def test_ranking_question_not_marked_needs_new_data(self):
        """(b) A question answerable from synthesize.ranked_genes must NOT be marked
        needs_new_data — the model sees the full ranking in the prompt."""
        payload = {
            "answer": (
                "The full ranking is: 1. TSC2 (score 0.95), 2. MTOR (score 0.88), "
                "3. RHEB (score 0.81)."
            ),
            "needs_new_data": False,
            "missing_agent": None,
        }
        out = answer_followup(
            "Show me the full ranking",
            self._RESULT_WITH_SYNTHESIS,
            runner=_ok_runner(payload),
        )
        self.assertFalse(out["needs_new_data"])
        self.assertIn("TSC2", out["answer"])
        self.assertIsNone(out["missing_agent"])

    def test_report_question_not_marked_needs_new_data(self):
        """(b) A question about the final report is answerable → not needs_new_data."""
        payload = {
            "answer": "The final report concludes TSC2 is ranked #1.",
            "needs_new_data": False,
            "missing_agent": None,
        }
        out = answer_followup(
            "What did the synthesis report conclude?",
            self._RESULT_WITH_SYNTHESIS,
            runner=_ok_runner(payload),
        )
        self.assertFalse(out["needs_new_data"])

    def test_empty_first_response_retried_once(self):
        """(c) When the first model call returns a JSON object without an 'answer' key
        (_parse_model_response sets _parse_failed=True), the runner is called a second
        time and the retry's good response is returned to the caller."""
        call_count = {"n": 0}

        def _retry_runner(cmd):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # First call: JSON object missing "answer" — triggers _parse_failed
                return _FakeProc(
                    stdout=json.dumps({"needs_new_data": False, "missing_agent": None}),
                    returncode=0,
                )
            # Second call (retry): well-formed response
            return _FakeProc(
                stdout=json.dumps({
                    "answer": "TSC2 is ranked first.",
                    "needs_new_data": False,
                    "missing_agent": None,
                }),
                returncode=0,
            )

        out = answer_followup(
            "What is the top-ranked gene?",
            self._RESULT_WITH_SYNTHESIS,
            runner=_retry_runner,
        )
        self.assertEqual(call_count["n"], 2, "runner must be called exactly twice (first + retry)")
        self.assertIn("TSC2", out["answer"])
        self.assertFalse(out["needs_new_data"])

    def test_retry_not_triggered_on_good_first_response(self):
        """Retry must NOT fire when the first response parses successfully — runner called once."""
        call_count = {"n": 0}

        def _counting_runner(cmd):
            call_count["n"] += 1
            return _FakeProc(
                stdout=json.dumps({
                    "answer": "TSC2 is the top target.",
                    "needs_new_data": False,
                    "missing_agent": None,
                }),
                returncode=0,
            )

        answer_followup(
            "What is the top gene?",
            self._RESULT_WITH_SYNTHESIS,
            runner=_counting_runner,
        )
        self.assertEqual(call_count["n"], 1, "runner must be called exactly once on success")

    def test_no_synthesize_block_no_crash(self):
        """(d) Older/simulated results without a synthesize block must not crash and
        must still produce a valid answer dict."""
        result_no_synthesis = {
            "query": _QUERY,
            "discover": {"dossier": _DOSSIER, "flags": {}},
            "consult": {"round1": _ROUND1, "round2": []},
            # no 'synthesize' key at all
        }
        payload = {
            "answer": "Based on dossier only.",
            "needs_new_data": False,
            "missing_agent": None,
        }
        out = answer_followup(
            "Summarize the evidence",
            result_no_synthesis,
            runner=_ok_runner(payload),
        )
        self.assertIsInstance(out, dict)
        self.assertIn("answer", out)
        self.assertFalse(out["needs_new_data"])

    def test_synthesize_block_no_ranked_genes_no_crash(self):
        """A synthesize block with only recommendation/confidence (no ranked_genes/report)
        is handled gracefully — backward-compatible with pre-ranking runs."""
        result_partial = {
            "query": _QUERY,
            "discover": {"dossier": _DOSSIER, "flags": {}},
            "consult": {"round1": _ROUND1, "round2": []},
            "synthesize": {"recommendation": "Proceed.", "confidence": "moderate"},
        }
        prompt = _build_prompt("What is the recommendation?", result_partial, citation_labels=[])
        # No FINAL RANKING or FINAL REPORT block (neither ranked_genes nor report present)
        self.assertNotIn("FINAL RANKING", prompt)
        self.assertNotIn("FINAL REPORT", prompt)
        # But recommendation/confidence appear in the header
        self.assertIn("Proceed.", prompt)

    def test_report_truncated_when_long(self):
        """A synthesize.report longer than 4000 chars is truncated with a note, not dropped."""
        long_report = "X" * 5000
        block = _build_synthesis_blocks({
            "recommendation": "ok",
            "confidence": "high",
            "report": long_report,
        })
        self.assertIn("FINAL REPORT", block)
        self.assertIn("truncated at 4000 chars", block)
        # The block should not contain more than the first 4000 'X' chars + annotation
        self.assertLess(block.count("X"), 4001)


if __name__ == "__main__":
    unittest.main()
