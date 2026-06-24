"""
tests/test_experiment_design.py — ED-1 fidelity lock for the ported Experiment Design tool.

Offline ($0) by default:
  * verbatim lock — the ported domain content (extraction_prompt.py / schema.py) contains the
    vendored original CHARACTER-FOR-CHARACTER (CONVENTIONS §4).
  * golden-structure lock — sample_extraction_jan6.json conforms to the JSON output contract
    (experiments[] with metadata/culture/imaging/treatments/plate_layout/timeline, {value,
    confidence, source} leaves, action_items, open_questions) and equals the vendored sample.
  * render_md runs offline (no LLM); honest errors on bad input (never a fabricated plan).

One live test runs extract() against a real vendored transcript; it SKIPS cleanly unless
ANTHROPIC_API_KEY is set and `anthropic` is installed (the engine stays stdlib-only; this is the
tool's own subprocess dep — same posture as aso-tox skipping without sklearn).

Run from sapphire-orchestrator/:
    python -m unittest tests.test_experiment_design -v
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

# repo root = .../sapphire-capability-map  (this file: <root>/sapphire-orchestrator/tests/...)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_TOOL = os.path.join(_ROOT, "tools", "experiment_design")
_VENDOR = os.path.join(_ROOT, "vendor", "design-form-agent")
if _TOOL not in sys.path:
    sys.path.insert(0, _TOOL)

import extract as ed  # noqa: E402  (the ported tool; anthropic is lazy-imported inside extract())

try:
    import anthropic  # noqa: F401
    _ANTHROPIC = True
except ImportError:
    _ANTHROPIC = False
_LIVE = bool(os.environ.get("ANTHROPIC_API_KEY")) and _ANTHROPIC

_CONF = {"high", "medium", "low", "unresolved"}
_EXP_SECTIONS = ("metadata", "culture", "imaging", "treatments", "plate_layout", "timeline")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _is_field(x) -> bool:
    """A {value, confidence, source} leaf with a valid confidence."""
    return (isinstance(x, dict) and "value" in x and "confidence" in x
            and "source" in x and x.get("confidence") in _CONF)


class TestVendorVerbatim(unittest.TestCase):
    """The proprietary domain content is ported character-for-character (CONVENTIONS §4)."""

    def test_extraction_prompt_verbatim(self):
        vendored = _read(os.path.join(_VENDOR, "extraction_prompt.py"))
        ported = _read(os.path.join(_TOOL, "extraction_prompt.py"))
        self.assertIn(vendored, ported,
                      "ported extraction_prompt.py must contain the vendored original verbatim")
        self.assertTrue(ported.startswith("#"), "ported file should carry an attribution header")

    def test_schema_verbatim(self):
        vendored = _read(os.path.join(_VENDOR, "schema.py"))
        ported = _read(os.path.join(_TOOL, "schema.py"))
        self.assertIn(vendored, ported, "ported schema.py must contain the vendored original verbatim")

    def test_domain_constants_intact(self):
        # The system prompt + MENUS_REFERENCE carry the proprietary vocabulary, unparaphrased.
        self.assertIn("QuasAr", ed.SYSTEM_PROMPT)
        self.assertIn("CheRiff", ed.SYSTEM_PROMPT)
        for token in ("Excitability, Synaptic", "Tyrodes", "GABAzine", "Mini Janus"):
            self.assertIn(token, ed.MENUS_REFERENCE, f"MENUS_REFERENCE missing {token!r}")
        self.assertIn("{transcript}", ed.EXTRACTION_PROMPT)


class TestGoldenStructure(unittest.TestCase):
    """The golden sample conforms to the JSON output contract and matches the vendored copy."""

    def setUp(self):
        self.golden = json.loads(_read(os.path.join(_TOOL, "sample_extraction_jan6.json")))

    def test_golden_equals_vendored(self):
        vendored = json.loads(_read(os.path.join(_VENDOR, "sample_extraction_jan6.json")))
        self.assertEqual(self.golden, vendored, "golden fixture must be a faithful copy of the vendored sample")

    def test_top_level_shape(self):
        for key in ("meeting_title", "meeting_date", "attendees", "experiments",
                    "action_items", "open_questions"):
            self.assertIn(key, self.golden, f"golden missing top-level {key}")
        self.assertIsInstance(self.golden["experiments"], list)
        self.assertGreaterEqual(len(self.golden["experiments"]), 1)

    def test_experiment_sections_and_field_triples(self):
        exp = self.golden["experiments"][0]
        for sect in _EXP_SECTIONS:
            self.assertIn(sect, exp, f"experiment missing section {sect!r}")
        # metadata leaves must be {value, confidence, source} triples with a valid confidence
        for k in ("project_code", "assay_type", "sub_assay_type", "round_number"):
            self.assertTrue(_is_field(exp["metadata"][k]),
                            f"metadata.{k} is not a valid {{value,confidence,source}} field: {exp['metadata'].get(k)}")
        # a non-vacuous content anchor (this golden is the Jan-6 inhibitory-neuron meeting)
        self.assertEqual(exp["metadata"]["assay_type"]["value"], "Synaptic")

    def test_action_items_and_open_questions_shape(self):
        self.assertTrue(all("description" in a for a in self.golden["action_items"]))
        self.assertTrue(all("question" in q for q in self.golden["open_questions"]))


class TestRenderMdOffline(unittest.TestCase):
    """render_md() formats the JSON with no LLM/network — runs on the golden fixture."""

    def test_render_md_on_golden(self):
        golden = json.loads(_read(os.path.join(_TOOL, "sample_extraction_jan6.json")))
        md = ed.render_md(golden)
        self.assertIsInstance(md, str)
        self.assertIn("# Meeting Extraction:", md)
        self.assertIn("## Experiment 1:", md)
        self.assertIn("Potassium titration", md)            # the golden's first experiment name
        self.assertIn("## Action Items", md)
        self.assertIn("## Open Questions", md)


class TestHonestErrors(unittest.TestCase):
    """Bad input degrades honestly — a clear ExtractionError, never a fabricated plan, no LLM call."""

    def test_missing_file(self):
        with self.assertRaises(ed.ExtractionError):
            ed.extract(os.path.join(tempfile.gettempdir(), "__no_such_transcript__.txt"))

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            p = f.name
        try:
            with self.assertRaises(ed.ExtractionError):
                ed.extract(p)
        finally:
            os.remove(p)

    def test_unsupported_suffix(self):
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False, mode="w") as f:
            f.write("some content")
            p = f.name
        try:
            with self.assertRaises(ed.ExtractionError):
                ed.extract(p)
        finally:
            os.remove(p)

    def test_missing_api_key(self):
        """A valid .txt but no ANTHROPIC_API_KEY -> clear error, before any LLM call."""
        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as f:
            f.write("Meeting transcript: we will run a synaptic assay.")
            p = f.name
        try:
            with self.assertRaises(ed.ExtractionError):
                ed.extract(p)
        finally:
            os.remove(p)
            if saved is not None:
                os.environ["ANTHROPIC_API_KEY"] = saved


@unittest.skipUnless(_LIVE, "live extraction needs ANTHROPIC_API_KEY + the anthropic package")
class TestLiveExtraction(unittest.TestCase):
    """Run the real tool on a vendored transcript; assert structural conformance (non-deterministic)."""

    def test_live_extract_vendored_pdf(self):
        pdf = os.path.join(_VENDOR, "test_data", "Follow up_ Aim 1 Inhibitory neuron experiments.pdf")
        if not os.path.exists(pdf):
            self.skipTest(f"vendored transcript not found: {pdf}")
        data = ed.extract(pdf)
        self.assertIn("experiments", data)
        self.assertIsInstance(data["experiments"], list)
        self.assertGreaterEqual(len(data["experiments"]), 1)
        exp = data["experiments"][0]
        for sect in _EXP_SECTIONS:
            self.assertIn(sect, exp, f"live extraction experiment missing {sect!r}")
        # renders without error
        self.assertIn("# Meeting Extraction:", ed.render_md(data))


if __name__ == "__main__":
    unittest.main(verbosity=2)
