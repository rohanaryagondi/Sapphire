"""
fill.py — Sapphire Experiment Design tool (ED-2): extracted plan -> filled design sheet.

Takes the structured plan produced by extract.py (ED-1) and produces the *filled
design sheet*:
  1. a form-ready JSON — Matt's schema, with a `design_sheet` validation block
     added alongside the (untouched) plan;
  2. a human-readable design doc (Markdown) — the ED-1 render plus a "Design Sheet
     Validation" section surfacing menu flags and a readiness rollup;
  3. (seam) the populated Quiver .xlsx design sheet — pending the canonical
     template + cell map (coordinated via dev/HELP.md).

MENU VALIDATION (the point of ED-2's safety net): values extracted for a CLOSED
single-select dropdown (Assay Types, Sub-Assay Types, Imaging Buffers, Temperature
Options) are checked against MENUS_REFERENCE — the verbatim dropdown vocabulary
ported in extraction_prompt.py. A value that is NOT an exact menu option is
FLAGGED for human review; it is never silently written into a dropdown cell. Open
menus ("...and others") and null values never flag.

DATA BOUNDARY (dev/CONVENTIONS.md §3): this step does NO network and NO LLM call —
it is a pure local transform over the already-extracted JSON + local files. Pure
stdlib: the optional .xlsx writer would import openpyxl lazily in THIS tool's
subprocess; the Sapphire engine stays stdlib-only and imports nothing here.

Usage:
  python tools/experiment_design/fill.py plan_extraction.json [--output-dir ./out]
                                          [--xlsx-template path/to/template.xlsx]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:  # script-run (this dir on sys.path)
    from extraction_prompt import MENUS_REFERENCE
    from extract import render_md
except ImportError:  # package-style import
    from .extraction_prompt import MENUS_REFERENCE
    from .extract import render_md


class FillError(RuntimeError):
    """Honest, user-facing failure (malformed extraction input).
    The tool degrades honestly — it never fabricates a sheet on bad input."""


class TemplateUnavailable(RuntimeError):
    """The .xlsx design template (or its cell map) isn't available yet.
    An honest skip, not a guessed layout — nothing gets half-written."""


# ── Menu parsing + validation ─────────────────────────────────────────
def _split_options(vals: str) -> list:
    """Split a menu's comma-separated options WITHOUT splitting commas inside
    parentheses — e.g. 'Mini Janus (3x to 1x, 200x to 1x)' stays a single option."""
    parts, depth, cur = [], 0, []
    for ch in vals:
        if ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def parse_menus(text: str = MENUS_REFERENCE) -> dict:
    """Parse the single-line 'Name: a, b, c' menus from the verbatim MENUS_REFERENCE.

    Returns {menu_name: {"values": set[str], "open": bool}}. A menu whose list
    ends in 'and others' is open (any value is valid). Nested/multi-line menus
    (e.g. 'Standard Blockers:') are skipped — they are not single-select dropdowns.
    The vocabulary stays single-sourced from extraction_prompt.py; never retyped here.
    """
    menus: dict = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("-") or ":" not in stripped:
            continue
        name, _, vals = stripped.partition(":")
        name, vals = name.strip(), vals.strip()
        if not vals:  # header line for a nested menu (e.g. "Standard Blockers:")
            continue
        items = _split_options(vals)
        is_open = any(it.lower() == "and others" for it in items)
        values = {it for it in items if it.lower() != "and others"}
        menus[name] = {"values": values, "open": is_open}
    return menus


_MENUS = parse_menus()

# Extraction field (section, key) -> menu name. ONLY closed, single-select
# dropdown fields are validated; free-text / open-menu fields (plate type, cell
# types) are not — they legitimately accept values outside the listed examples.
_MENU_FIELDS = [
    (("metadata", "assay_type"), "Assay Types"),
    (("metadata", "sub_assay_type"), "Sub-Assay Types"),
    (("imaging", "imaging_buffer"), "Imaging Buffers"),
    (("imaging", "temperature"), "Temperature Options"),
]


def validate_menus(extraction: dict, menus: dict = _MENUS) -> list:
    """Flag extracted values that are not valid options for a closed dropdown menu.

    Returns a list of warning dicts (one per offending field):
      {experiment_index, experiment_name, field, menu, value, valid_options}
    A flagged value is surfaced for human review — NEVER silently written into a
    dropdown cell (the ED-2 DoD). Open menus and null/empty values never flag;
    honest-empty -> returns [] when every dropdown value is on-menu.
    """
    warnings: list = []
    experiments = extraction.get("experiments", []) if isinstance(extraction, dict) else []
    for i, exp in enumerate(experiments, 1):
        if not isinstance(exp, dict):
            continue
        exp_name = exp.get("experiment_name") or f"Experiment {i}"
        for (section, key), menu_name in _MENU_FIELDS:
            sec = exp.get(section)
            if not isinstance(sec, dict):
                continue
            field = sec.get(key)
            if isinstance(field, dict):
                value = field.get("value")
            elif isinstance(field, str):
                value = field  # degraded upstream (bare scalar) — still validate, don't skip
            else:
                continue
            if value in (None, ""):
                continue
            menu = menus.get(menu_name)
            if not menu or menu["open"]:
                continue
            if value not in menu["values"]:
                warnings.append({
                    "experiment_index": i,
                    "experiment_name": exp_name,
                    "field": f"{section}.{key}",
                    "menu": menu_name,
                    "value": value,
                    "valid_options": sorted(menu["values"]),
                })
    return warnings


def _count_unresolved(obj) -> int:
    """Count {value, confidence, source} leaves whose confidence is 'unresolved'."""
    if isinstance(obj, dict):
        if obj.get("confidence") == "unresolved":
            return 1
        return sum(_count_unresolved(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_count_unresolved(v) for v in obj)
    return 0


# ── Fill: extraction -> form-ready sheet ──────────────────────────────
def fill(extraction: dict) -> dict:
    """Turn an extracted plan into the filled design sheet (form-ready JSON).

    Returns the extraction (Matt's schema, plan untouched) with an additive
    `design_sheet` block carrying the menu-validation result + a readiness rollup.
    Honest failure: a non-dict / structurally-invalid extraction -> FillError
    (never a fabricated sheet).
    """
    if not isinstance(extraction, dict):
        raise FillError("extraction must be a JSON object (dict)")
    if "experiments" not in extraction:
        raise FillError("extraction has no 'experiments' key — not a valid plan")
    if not isinstance(extraction["experiments"], list):
        raise FillError("'experiments' must be a list")

    menu_warnings = validate_menus(extraction)

    filled = dict(extraction)  # shallow copy: add a sibling block, never mutate the plan
    filled["design_sheet"] = {
        "menu_validation": menu_warnings,
        "menu_ok": not menu_warnings,
        "experiment_count": len(extraction["experiments"]),
        "unresolved_fields": _count_unresolved(extraction["experiments"]),
    }
    return filled


# ── Design-doc renderer ───────────────────────────────────────────────
def render_design_doc(filled: dict) -> str:
    """Render the human-readable design doc: the ED-1 plan render + a validation section.

    Reuses extract.render_md for the per-field provenance/confidence body, then
    appends "Design Sheet Validation" (readiness rollup + menu flags for review).
    """
    body = render_md(filled)  # render_md ignores the additive design_sheet block
    ds = filled.get("design_sheet", {})
    out = [body, "\n---\n", "## Design Sheet Validation\n"]
    out.append(f"- **Experiments:** {ds.get('experiment_count', 0)}")
    out.append(
        f"- **Unresolved fields:** {ds.get('unresolved_fields', 0)} "
        "(need a human decision before the sheet is final)"
    )
    warnings = ds.get("menu_validation", [])
    if not warnings:
        out.append("- **Menu check:** ✅ every dropdown value is a valid menu option")
    else:
        out.append(
            f"- **Menu check:** ⚠️ {len(warnings)} value(s) are NOT an exact dropdown "
            "option — review before writing the sheet:"
        )
        for w in warnings:
            opts = ", ".join(w["valid_options"])
            out.append(
                f"  - Exp {w['experiment_index']} ({w['experiment_name']}) · "
                f"`{w['field']}` = **{w['value']}** is not in *{w['menu']}* ({opts})"
            )
    return "\n".join(out)


# ── xlsx writer (SEAM — pending the canonical template) ───────────────
def write_xlsx(filled: dict, template_path=None, out_path=None):
    """Populate Quiver's .xlsx design template with the filled sheet — PENDING SEAM.

    When wired, this would open the canonical template with openpyxl (lazy import,
    THIS tool's subprocess only), write each field to its mapped cell, and refuse
    to write any menu-flagged value into a dropdown cell (route it to a 'review'
    note instead). It is blocked on two things being provided via dev/HELP.md
    (experiment-design-ed2-xlsx-template): the canonical .xlsx template + its cell
    map (named ranges), and where filled sheets should land.

    Until then this raises TemplateUnavailable so a sheet is never half-written or
    guessed. fill() + the design-doc MD are complete and unblocked without it.
    """
    raise TemplateUnavailable(
        "xlsx writer is a pending seam: it needs Quiver's canonical .xlsx design "
        "template + its cell map (named ranges) and the target location for filled "
        "sheets — tracked in dev/HELP.md (experiment-design-ed2-xlsx-template). "
        "The form-ready JSON and the design-doc Markdown are written regardless."
    )


# ── CLI ───────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Fill the Quiver experiment design sheet from an extracted plan JSON (extract.py / ED-1 output)."
    )
    parser.add_argument("extraction", help="Path to *_extraction.json (from extract.py)")
    parser.add_argument("--output-dir", default=".", help="Directory for output files (default: .)")
    parser.add_argument(
        "--xlsx-template", default=None,
        help="Path to Quiver's .xlsx design template (optional; xlsx write is a pending seam)",
    )
    args = parser.parse_args()

    src = Path(args.extraction)
    if not src.exists():
        print(f"ERROR: extraction not found: {src}")
        raise SystemExit(2)
    try:
        extraction = json.loads(src.read_text(encoding="utf-8-sig"))  # tolerate a BOM (Excel/Windows exports)
    except json.JSONDecodeError as exc:
        print(f"ERROR: not valid JSON ({src}): {exc}")
        raise SystemExit(2)

    try:
        filled = fill(extraction)
    except FillError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(2)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem
    if stem.endswith("_extraction"):
        stem = stem[: -len("_extraction")]
    json_out = out_dir / f"{stem}_design_sheet.json"
    md_out = out_dir / f"{stem}_design_sheet.md"
    json_out.write_text(json.dumps(filled, indent=2), encoding="utf-8")
    md_out.write_text(render_design_doc(filled), encoding="utf-8")
    print(f"Wrote {json_out}")
    print(f"Wrote {md_out}")

    ds = filled["design_sheet"]
    if ds["menu_validation"]:
        print(
            f"NOTE: {len(ds['menu_validation'])} value(s) are not exact dropdown "
            "options — see the design doc's 'Design Sheet Validation' section."
        )
    if args.xlsx_template is not None:
        try:
            write_xlsx(filled, args.xlsx_template, out_dir / f"{stem}_design_sheet.xlsx")
            print(f"Wrote {out_dir / f'{stem}_design_sheet.xlsx'}")
        except TemplateUnavailable as exc:
            print(f"NOTE: xlsx not written — {exc}")


if __name__ == "__main__":
    main()
