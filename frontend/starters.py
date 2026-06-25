"""CNS-reframed starter prompts for the Sapphire control surface.

Public identifiers only (gene symbols, disease terms, drug names) — never internal candidate
IDs. Each starter is a deliberative / CNS-decision query that exercises the full firm
(dossier + roundtable + synthesis), not a one-shot lookup.
"""
from __future__ import annotations

STARTERS = [
    {
        "label": "TSC2 — viable CNS target?",
        "message": "Is TSC2 a viable target in tuberous sclerosis? Convene the firm.",
        "icon": "/public/favicon.svg",
    },
    {
        "label": "ASO for SCN2A DEE — would FDA/payers back it?",
        "message": ("Would FDA and payers back an antisense oligonucleotide for SCN2A "
                    "developmental and epileptic encephalopathy?"),
        "icon": "/public/favicon.svg",
    },
    {
        "label": "KCNQ2 — go / no-go on a small molecule",
        "message": "Should we advance a small-molecule program against KCNQ2 for neonatal epilepsy?",
        "icon": "/public/favicon.svg",
    },
    {
        "label": "Amyloid precedent — risk read",
        "message": ("Given the aducanumab/lecanemab amyloid precedents, what is the regulatory "
                    "risk for a new anti-amyloid program in early Alzheimer's?"),
        "icon": "/public/favicon.svg",
    },
    {
        "label": "STXBP1 — de-risk the target",
        "message": "De-risk STXBP1 as a CNS target: what would the roundtable conclude?",
        "icon": "/public/favicon.svg",
    },
]
