"""
Tests for reinvoke.py — WO-9 Phase 5 targeted re-invocation of ONE agent/tool.

All tests are hermetic: the Bucket-1 (claude-subagent) path is exercised via an
injected `runner` (no real `claude -p` subprocess); the Q-Models path via a fake
`QModelsClient`. Mirrors test_followup.py's fixture style.
"""
from __future__ import annotations

import json
import os
import sys
import unittest

_ORCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ORCH_DIR not in sys.path:
    sys.path.insert(0, _ORCH_DIR)

from reinvoke import reinvoke_agent


class _FakeProc:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.returncode = returncode


def _claude_ok_runner(structured_output: dict):
    """A runner that mimics `claude -p --output-format json`'s envelope shape."""
    def run(cmd):
        return _FakeProc(json.dumps({"structured_output": structured_output}))
    return run


def _claude_raising_runner(cmd):
    raise RuntimeError("simulated subprocess failure")


class _FakeQModelsClient:
    def __init__(self, tools, call_result=None, raise_on_call=None):
        self._tools = tools
        self._call_result = call_result
        self._raise_on_call = raise_on_call

    def tools(self):
        return list(self._tools)

    def call(self, tool_id, inputs):
        if self._raise_on_call is not None:
            raise self._raise_on_call
        return dict(self._call_result or {})


_SOURCE_RESULT = {
    "query": "Is TSC2 a viable target in tuberous sclerosis complex?",
    "plan": {"disease": "tuberous sclerosis complex"},
}


class TestReinvokeBucket1Success(unittest.TestCase):
    def test_semantic_agent_reinvocation_returns_enriched_new_facts(self):
        payload = {
            "candidate": "TSC2",
            "facts": [
                {"value": "FAERS shows elevated AE reports for mTOR inhibitors.",
                 "source": "FAERS", "tier": "T2"},
            ],
        }
        out = reinvoke_agent(
            "post-market-safety", _SOURCE_RESULT,
            runner=_claude_ok_runner(payload),
        )
        self.assertTrue(out["ok"], out.get("error"))
        self.assertEqual(out["agent_id"], "post-market-safety")
        self.assertEqual(len(out["new_facts"]), 1)
        fact = out["new_facts"][0]
        # public-safe enrichment mirrors live_engine.py: plane derived, agent_id stamped.
        self.assertIn("plane", fact)
        self.assertEqual(fact["agent_id"], "post-market-safety")
        self.assertIn("provenance", fact)
        self.assertIsNone(out["error"])
        self.assertTrue(out["engagement_id"])

    def test_refined_query_scopes_the_candidate_over_the_original_query(self):
        """A refined_query naming a DIFFERENT gene must scope the dispatch's candidate —
        never silently fall back to the original run's query when a refinement is given."""
        seen_inputs = {}

        def capturing_runner(cmd):
            # cmd[-2] holds the `--json-schema` value's preceding text; instead, capture
            # inputs by inspecting the prompt (built into cmd via build_prompt/-p).
            prompt = cmd[cmd.index("-p") + 1] if "-p" in cmd else ""
            seen_inputs["prompt"] = prompt
            return _FakeProc(json.dumps({
                "structured_output": {"candidate": "SCN2A", "facts": [
                    {"value": "SCN2A signal found.", "source": "X", "tier": "T2"},
                ]},
            }))

        out = reinvoke_agent(
            "post-market-safety", _SOURCE_RESULT,
            refined_query="What about SCN2A specifically?",
            runner=capturing_runner,
        )
        self.assertTrue(out["ok"], out.get("error"))
        self.assertIn("SCN2A", seen_inputs["prompt"])
        self.assertNotIn('"TSC2"', seen_inputs["prompt"])


class TestReinvokeBucket1Failure(unittest.TestCase):
    def test_dispatch_exception_degrades_honestly_never_raises(self):
        out = reinvoke_agent("post-market-safety", _SOURCE_RESULT, runner=_claude_raising_runner)
        self.assertFalse(out["ok"])
        self.assertEqual(out["new_facts"], [])
        self.assertIsNotNone(out["error"])

    def test_agent_abstain_no_facts_degrades_honestly(self):
        """A schema-valid but empty facts list is an honest non-result, not evidence."""
        payload = {"candidate": "TSC2", "facts": []}
        out = reinvoke_agent("post-market-safety", _SOURCE_RESULT, runner=_claude_ok_runner(payload))
        self.assertFalse(out["ok"])
        self.assertEqual(out["new_facts"], [])
        self.assertIsNotNone(out["error"])

    def test_malformed_output_never_raises_and_degrades(self):
        def bad_runner(cmd):
            return _FakeProc("not json at all", returncode=0)
        out = reinvoke_agent("post-market-safety", _SOURCE_RESULT, runner=bad_runner)
        self.assertFalse(out["ok"])
        self.assertEqual(out["new_facts"], [])


class TestReinvokeQModels(unittest.TestCase):
    def test_qmodels_tool_success(self):
        client = _FakeQModelsClient(
            tools=[{"id": "dti", "label": "DTI / Binder Triage", "tier": "local-cpu", "status": "live-local"}],
            call_result={"ok": True, "tool_id": "dti", "provenance": "live-local",
                        "model": "DTI / Binder Triage", "out": "pKi=7.2"},
        )
        out = reinvoke_agent("dti", _SOURCE_RESULT, qmodels_client=client)
        self.assertTrue(out["ok"], out.get("error"))
        self.assertEqual(out["agent_id"], "dti")
        self.assertEqual(len(out["new_facts"]), 1)
        self.assertEqual(out["new_facts"][0]["provenance"], "live-local")
        self.assertEqual(out["new_facts"][0]["agent_id"], "dti")

    def test_qmodels_tool_unavailable_degrades_honestly(self):
        client = _FakeQModelsClient(
            tools=[{"id": "dti", "label": "DTI / Binder Triage", "tier": "local-cpu", "status": "live-local"}],
            call_result={"ok": False, "tool_id": "dti", "provenance": "unavailable",
                        "note": "endpoint down"},
        )
        out = reinvoke_agent("dti", _SOURCE_RESULT, qmodels_client=client)
        self.assertFalse(out["ok"])
        self.assertEqual(out["new_facts"], [])
        self.assertIsNotNone(out["error"])

    def test_qmodels_call_exception_degrades_honestly_never_raises(self):
        client = _FakeQModelsClient(
            tools=[{"id": "dti", "label": "DTI / Binder Triage"}],
            raise_on_call=RuntimeError("boom"),
        )
        out = reinvoke_agent("dti", _SOURCE_RESULT, qmodels_client=client)
        self.assertFalse(out["ok"])
        self.assertEqual(out["new_facts"], [])
        self.assertIn("boom", out["error"])


class TestReinvokeUnknownAgent(unittest.TestCase):
    def test_unknown_agent_id_degrades_honestly(self):
        client = _FakeQModelsClient(tools=[{"id": "dti", "label": "DTI"}])
        out = reinvoke_agent("not-a-real-agent-or-tool", _SOURCE_RESULT, qmodels_client=client)
        self.assertFalse(out["ok"])
        self.assertEqual(out["new_facts"], [])
        self.assertIsNotNone(out["error"])

    def test_empty_agent_id_degrades_honestly(self):
        out = reinvoke_agent("", _SOURCE_RESULT)
        self.assertFalse(out["ok"])
        self.assertIsNotNone(out["error"])

    def test_none_agent_id_never_raises(self):
        out = reinvoke_agent(None, _SOURCE_RESULT)  # type: ignore[arg-type]
        self.assertFalse(out["ok"])

    def test_persona_id_is_not_a_valid_reinvocation_target(self):
        """Bucket-2 personas (company-partner, ex-fda-regulator, ...) are explicitly
        out of scope for this phase (roundtable re-invocation) — a persona id must
        degrade the same as any other unknown target, never silently dispatch it."""
        client = _FakeQModelsClient(tools=[])
        out = reinvoke_agent("company-partner", _SOURCE_RESULT, qmodels_client=client)
        self.assertFalse(out["ok"])
        self.assertIsNotNone(out["error"])


class TestReinvokeSourceResultHandling(unittest.TestCase):
    def test_none_source_result_never_raises(self):
        client = _FakeQModelsClient(
            tools=[{"id": "dti", "label": "DTI"}],
            call_result={"ok": True, "tool_id": "dti", "provenance": "live-local", "out": "x"},
        )
        out = reinvoke_agent("dti", None, qmodels_client=client)
        self.assertIsInstance(out, dict)
        self.assertIn("ok", out)


if __name__ == "__main__":
    unittest.main()
