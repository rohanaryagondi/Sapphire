"""Offline tests for trace_view.py — STDLIB only; no network calls."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Make sure the orchestrator package root is importable when tests run from
# sapphire-orchestrator/ via: python -m unittest tests.test_trace_view
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_view import render, main  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic trace fixtures
# ---------------------------------------------------------------------------

_OPEN = {
    "type": "engagement_open",
    "engagement_id": "test-eid-001",
    "plan": {
        "query": "Is KRAS-G12C druggable in NSCLC?",
        "deliverable": "target-assessment",
        "disease": "NSCLC",
        "modality": "small molecule",
    },
    "ts": "2026-06-20T10:00:00+00:00",
}

_AGENT_FINDINGS = {
    "engagement_id": "test-eid-001",
    "agent_id": "moat-researcher",
    "kind": "findings",
    "inputs_hash": "abc123",
    "status": "ok",
    "provenance": "moat-real",
    "error": None,
    "repairs": [],
    "guardrails_run": [],
    "output": {
        "findings": [
            {"fact": "KRAS-G12C covalent targeting validated", "source": "PMID:111"},
            {"fact": "AMG-510 shows 36% ORR in NSCLC", "source": "PMID:222"},
        ]
    },
    "ts": "2026-06-20T10:01:00+00:00",
}

_AGENT_VERDICT = {
    "engagement_id": "test-eid-001",
    "agent_id": "red-team",
    "kind": "verdict",
    "inputs_hash": "def456",
    "status": "abstained",
    "provenance": "emet-live",
    "error": None,
    "repairs": [],
    "guardrails_run": ["data-boundary-check", "hallucination-screen"],
    "output": {"stance": "insufficient resistance data"},
    "ts": "2026-06-20T10:02:00+00:00",
}

_CLOSE = {
    "type": "engagement_close",
    "engagement_id": "test-eid-001",
    "synthesis": {
        "recommendation": "Advance KRAS-G12C program with resistance profiling study",
        "consensus": "partial",
        "confidence": {"biology": 0.8, "feasibility": 0.6},
    },
    "ts": "2026-06-20T10:03:00+00:00",
}


def _write_trace(directory: str, eid: str, rows: list[dict]) -> Path:
    eid_dir = Path(directory) / eid
    eid_dir.mkdir(parents=True, exist_ok=True)
    trace = eid_dir / "trace.jsonl"
    with open(trace, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return trace


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTraceView(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["SAPPHIRE_ENGAGEMENTS_DIR"] = self.tmp
        self.eid = "test-eid-001"
        _write_trace(
            self.tmp,
            self.eid,
            [_OPEN, _AGENT_FINDINGS, _AGENT_VERDICT, _CLOSE],
        )

    def tearDown(self):
        os.environ.pop("SAPPHIRE_ENGAGEMENTS_DIR", None)

    # -- render: key fields present -----------------------------------------

    def test_render_contains_agent_ids(self):
        out = render(self.eid)
        self.assertIn("moat-researcher", out)
        self.assertIn("red-team", out)

    def test_render_contains_provenance(self):
        out = render(self.eid)
        self.assertIn("moat-real", out)

    def test_render_abstained_glyph_or_status(self):
        out = render(self.eid)
        # Either the glyph or the word "abstained" must appear
        self.assertTrue("⚠" in out or "abstained" in out)

    def test_render_guardrail_name(self):
        out = render(self.eid)
        self.assertIn("data-boundary-check", out)

    def test_render_recommendation(self):
        out = render(self.eid)
        self.assertIn("KRAS-G12C program", out)

    def test_render_agent_count(self):
        out = render(self.eid)
        # Footer must mention the total agent count (2)
        self.assertIn("2", out)

    def test_render_disease_in_header(self):
        out = render(self.eid)
        self.assertIn("NSCLC", out)

    def test_render_findings_output_summary(self):
        out = render(self.eid)
        # findings block: should summarize fact count
        self.assertIn("finding", out)

    # -- missing trace -------------------------------------------------------

    def test_render_missing_returns_no_trace_line(self):
        out = render("nonexistent-eid-xyz")
        self.assertIn("no trace for", out)
        self.assertIn("nonexistent-eid-xyz", out)

    def test_render_missing_does_not_raise(self):
        try:
            render("nonexistent-eid-xyz")
        except Exception as exc:  # noqa: BLE001
            self.fail(f"render raised an exception for missing trace: {exc}")

    # -- full mode -----------------------------------------------------------

    def test_render_full_includes_json(self):
        out = render(self.eid, full=True)
        # Full JSON should show the raw fact text
        self.assertIn("AMG-510", out)

    # -- non-dict output does not crash -------------------------------------

    def test_render_non_dict_output_does_not_raise(self):
        """A trace row with a string output must not crash render (FIX 3)."""
        eid = "test-eid-nondict"
        _write_trace(self.tmp, eid, [
            {**_OPEN, "engagement_id": eid},
            {
                "engagement_id": eid,
                "agent_id": "string-output-agent",
                "kind": "findings",
                "inputs_hash": "aaa",
                "status": "ok",
                "provenance": "test",
                "error": None,
                "repairs": [],
                "guardrails_run": [],
                "output": "raw string output from agent",
                "ts": "2026-06-22T00:00:00+00:00",
            },
            {**_CLOSE, "engagement_id": eid},
        ])
        try:
            out = render(eid)
        except Exception as exc:
            self.fail(f"render raised on non-dict output: {exc}")
        self.assertIn("string-output-agent", out)

    # -- main() return codes -------------------------------------------------

    def test_main_returns_0_for_valid_eid(self):
        rc = main([self.eid])
        self.assertEqual(rc, 0)

    def test_main_returns_nonzero_for_missing_arg(self):
        rc = main([])
        self.assertNotEqual(rc, 0)

    def test_main_survives_cp1252_stdout(self):
        # Regression: rendering a trace with a non-ASCII glyph (✓) to a legacy
        # codepage stdout must not raise UnicodeEncodeError (Windows cp1252).
        import io
        real_stdout = sys.stdout
        # A text stream whose encoding cannot represent ✓ (cp1252 has no U+2713).
        sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
        try:
            rc = main([self.eid])
        finally:
            sys.stdout = real_stdout
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
