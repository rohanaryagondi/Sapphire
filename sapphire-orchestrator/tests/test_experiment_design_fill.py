"""
tests/test_experiment_design_fill.py — ED-2 lock for the design-sheet filler (fill.py).

Fully offline ($0, no LLM, no network): fill.py is a pure local transform over an
already-extracted plan JSON.

Covers:
  * menu parsing — closed vs open menus pulled from the verbatim MENUS_REFERENCE;
  * menu VALIDATION — the ED-2 safety net: an off-menu dropdown value is FLAGGED
    (caught), an on-menu value passes, nulls/open-menus never flag (non-vacuous);
  * fill() — produces the form-ready sheet, plan preserved, honest errors;
  * render_design_doc() — emits the validation section offline;
  * write_xlsx() — honest pending seam (raises TemplateUnavailable, never guesses);
  * CLI — writes JSON + design MD and exits 0; honest exit 2 on bad input.

Run from sapphire-orchestrator/:
    python -m unittest tests.test_experiment_design_fill -v
"""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

# repo root = .../sapphire-capability-map  (this file: <root>/sapphire-orchestrator/tests/...)
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_TOOL = os.path.join(_ROOT, "tools", "experiment_design")
_GOLDEN = os.path.join(_TOOL, "sample_extraction_jan6.json")
if _TOOL not in sys.path:
    sys.path.insert(0, _TOOL)

import fill as ed2  # noqa: E402  (the ED-2 filler; pure stdlib, import-safe without anthropic)


def _golden() -> dict:
    with open(_GOLDEN, encoding="utf-8") as f:
        return json.load(f)


class TestParseMenus(unittest.TestCase):
    """Menus are parsed from the verbatim MENUS_REFERENCE (single-sourced, not retyped)."""

    def setUp(self):
        self.menus = ed2.parse_menus()

    def test_closed_menu_assay_types(self):
        m = self.menus["Assay Types"]
        self.assertFalse(m["open"])
        self.assertEqual(m["values"], {"Excitability", "Synaptic", "Other"})

    def test_closed_menu_imaging_buffers(self):
        m = self.menus["Imaging Buffers"]
        self.assertFalse(m["open"])
        self.assertEqual(m["values"], {"Tyrodes", "Brainphys", "Other"})

    def test_open_menu_plate_types(self):
        # "...and others" -> open menu; the sentinel is not a value
        m = self.menus["Plate Types"]
        self.assertTrue(m["open"])
        self.assertIn("96-well Ibidi", m["values"])
        self.assertNotIn("and others", {v.lower() for v in m["values"]})

    def test_nested_menu_skipped(self):
        # 'Standard Blockers:' is a multi-line nested menu, not a single-select dropdown
        self.assertNotIn("Standard Blockers", self.menus)

    def test_paren_comma_menu_not_split(self):
        # commas INSIDE parentheses must not split an option (paren-aware splitter)
        m = self.menus["Compound Addition Protocols"]
        self.assertEqual(len(m["values"]), 4)
        self.assertIn("Mini Janus (3x to 1x, 200x to 1x, 500x to 1x, 1000x to 1x)", m["values"])
        self.assertIn("Manual single pipette", m["values"])


class TestValidateMenus(unittest.TestCase):
    """The ED-2 DoD: an invalid dropdown value is CAUGHT, not silently written."""

    def test_golden_flags_only_the_modified_buffer(self):
        warns = ed2.validate_menus(_golden())
        # Exactly one off-menu value in the golden: exp-1 buffer "Tyrodes (modified with KMeSO4)"
        self.assertEqual(len(warns), 1, warns)
        w = warns[0]
        self.assertEqual(w["experiment_index"], 1)
        self.assertEqual(w["field"], "imaging.imaging_buffer")
        self.assertEqual(w["menu"], "Imaging Buffers")
        self.assertEqual(w["value"], "Tyrodes (modified with KMeSO4)")
        self.assertIn("Tyrodes", w["valid_options"])

    def test_exact_menu_value_does_not_flag(self):
        # exp-2 imaging_buffer is exactly "Tyrodes" (on-menu) -> no warning for it
        warns = ed2.validate_menus(_golden())
        exp2_buffer = [w for w in warns if w["experiment_index"] == 2 and w["field"] == "imaging.imaging_buffer"]
        self.assertEqual(exp2_buffer, [])

    def test_invalid_closed_menu_value_is_caught(self):
        bad = {"experiments": [{
            "experiment_name": "X",
            "metadata": {"assay_type": {"value": "Bogus", "confidence": "high", "source": "t"}},
        }]}
        warns = ed2.validate_menus(bad)
        self.assertEqual(len(warns), 1)
        self.assertEqual(warns[0]["menu"], "Assay Types")
        self.assertEqual(warns[0]["value"], "Bogus")

    def test_valid_closed_menu_value_passes(self):
        good = {"experiments": [{
            "experiment_name": "X",
            "metadata": {"assay_type": {"value": "Synaptic", "confidence": "high", "source": "t"}},
        }]}
        self.assertEqual(ed2.validate_menus(good), [])

    def test_null_value_never_flags(self):
        nul = {"experiments": [{
            "metadata": {"assay_type": {"value": None, "confidence": "unresolved", "source": "t"}},
        }]}
        self.assertEqual(ed2.validate_menus(nul), [])

    def test_open_menu_field_not_validated(self):
        # plate_type is an open menu ("...and others") AND not in _MENU_FIELDS -> never flags
        op = {"experiments": [{
            "culture": {"plate_type": {"value": "some bespoke plate", "confidence": "low", "source": "t"}},
        }]}
        self.assertEqual(ed2.validate_menus(op), [])


class TestFill(unittest.TestCase):
    """fill() produces the form-ready sheet; the plan is preserved untouched."""

    def test_design_sheet_block(self):
        filled = ed2.fill(_golden())
        ds = filled["design_sheet"]
        self.assertEqual(ds["experiment_count"], 3)
        self.assertFalse(ds["menu_ok"])           # the golden has one off-menu buffer
        self.assertEqual(len(ds["menu_validation"]), 1)
        self.assertGreater(ds["unresolved_fields"], 0)

    def test_plan_preserved_unmodified(self):
        g = _golden()
        filled = ed2.fill(copy.deepcopy(g))
        # every original top-level plan key survives byte-equal (only design_sheet is added)
        for k, v in g.items():
            self.assertEqual(filled[k], v)
        self.assertEqual(set(filled) - set(g), {"design_sheet"})

    def test_clean_plan_reports_menu_ok(self):
        clean = {"experiments": [{
            "experiment_name": "X",
            "metadata": {"assay_type": {"value": "Synaptic", "confidence": "high", "source": "t"}},
            "imaging": {"imaging_buffer": {"value": "Tyrodes", "confidence": "high", "source": "t"}},
        }]}
        ds = ed2.fill(clean)["design_sheet"]
        self.assertTrue(ds["menu_ok"])
        self.assertEqual(ds["menu_validation"], [])


class TestRenderDesignDoc(unittest.TestCase):
    """The design doc renders offline and surfaces the validation section."""

    def test_validation_section_with_flag(self):
        doc = ed2.render_design_doc(ed2.fill(_golden()))
        self.assertIn("## Design Sheet Validation", doc)
        self.assertIn("Menu check", doc)
        self.assertIn("Tyrodes (modified with KMeSO4)", doc)   # the flagged value surfaced
        self.assertIn("Imaging Buffers", doc)

    def test_clean_plan_shows_menu_ok(self):
        clean = {"experiments": [{
            "experiment_name": "X",
            "imaging": {"imaging_buffer": {"value": "Tyrodes", "confidence": "high", "source": "t"}},
        }]}
        doc = ed2.render_design_doc(ed2.fill(clean))
        self.assertIn("every dropdown value is a valid menu option", doc)


class TestWriteXlsxSeam(unittest.TestCase):
    """The .xlsx writer is an honest pending seam — it never guesses a layout."""

    def test_write_xlsx_raises_template_unavailable(self):
        with self.assertRaises(ed2.TemplateUnavailable):
            ed2.write_xlsx(ed2.fill(_golden()))

    @unittest.skip("real .xlsx population pending Quiver's canonical template + cell map "
                   "(dev/HELP.md: experiment-design-ed2-xlsx-template)")
    def test_real_xlsx_write(self):  # pragma: no cover - documents the pending deliverable
        pass


class TestHonestErrors(unittest.TestCase):
    """Malformed input -> FillError; never a fabricated sheet."""

    def test_non_dict(self):
        with self.assertRaises(ed2.FillError):
            ed2.fill(["not", "a", "dict"])

    def test_missing_experiments(self):
        with self.assertRaises(ed2.FillError):
            ed2.fill({"meeting_title": "x"})

    def test_experiments_not_a_list(self):
        with self.assertRaises(ed2.FillError):
            ed2.fill({"experiments": {"oops": "dict"}})


class TestCLI(unittest.TestCase):
    """End-to-end CLI: writes the two artifacts and exits 0; honest exit 2 on bad input."""

    def test_cli_writes_json_and_md(self):
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(
                [sys.executable, os.path.join(_TOOL, "fill.py"), _GOLDEN, "--output-dir", d],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            js = os.path.join(d, "sample_extraction_jan6_design_sheet.json")
            md = os.path.join(d, "sample_extraction_jan6_design_sheet.md")
            self.assertTrue(os.path.exists(js), proc.stdout)
            self.assertTrue(os.path.exists(md), proc.stdout)
            with open(js, encoding="utf-8") as f:
                self.assertIn("design_sheet", json.load(f))

    def test_cli_missing_file_exits_2(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(_TOOL, "fill.py"), os.path.join(_TOOL, "nope.json")],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("not found", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
