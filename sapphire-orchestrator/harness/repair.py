"""Bounded-repair re-prompt builder (spec §A.4). Surgical: prior output + exact
failing paths + 'return the corrected object only'."""
from __future__ import annotations

import json


def repair_prompt(prior_output, errors) -> str:
    prior = json.dumps(prior_output, indent=2) if prior_output is not None else "(no prior output)"
    problems = "\n".join(f"  - {e}" for e in (errors or []))
    return (
        "Your previous output did not satisfy its contract. Fix exactly these problems:\n"
        f"{problems}\n\n"
        "Your previous output was:\n"
        f"{prior}\n\n"
        "Return ONLY the corrected structured object (the JSON schema is enforced). "
        "Do not add commentary."
    )
