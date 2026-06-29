# -*- coding: utf-8 -*-
"""
Sapphire Orchestrator — the end-to-end engine.

Executes the two-bucket "firm" defined in AGENTS.md as real control flow:

    triage -> scope -> engagement plan        (Engagement Lead, control)
      -> Bucket 1: facts -> dossier           (fact agents + Research Manager)
      -> Bucket 2: roundtable (2 rounds)       (Roundtable Moderator + partners)
      -> synthesis                            (Engagement Lead)

This is the LOGIC layer. It is deterministic, stdlib-only, and runs at $0.

Demo fidelity (see CLAUDE.md): the *control flow, dossier slotting, Research-Manager
completeness/contradiction/veto/divergence rules, panel seating, two-round spread, and
synthesis assembly* are all real, computed here. The *facts and persona verdicts* are
supplied by providers — in the demo they come from the captured scenario evidence packs
(sapphire-orchestrator/scenarios/<id>.json, grounded in live EMET runs + Q-Models mocks +
real persona-agent deliberation). In production the same seams call live EMET (Playwright),
Q-Models (AWS), and persona subagents (LLM). No contract changes — only the substrate.

The PLANNER (triage/scope/seat) is fully live for ANY query — that is the front-facing
intake. For a query that maps to a shipped scenario, run() returns the full canned run;
for a novel query it returns the plan + a note that live agents must run (via /sapphire).

Usage:
    from orchestrator import Orchestrator
    orc = Orchestrator()
    run = orc.run("nav1_8")                 # full end-to-end run (canonical dict)
    run = orc.run_query("rank Nav1.8 pain targets")   # query -> scenario or plan-only
    plan = orc.plan_only("is KCNQ2 fundable for epilepsy?")  # planner for any query
"""

from __future__ import annotations

import json
import os
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
SCENARIO_DIR = os.path.join(HERE, "scenarios")
QMODELS_DIR = os.path.join(HERE, "qmodels")

# --- which shipped scenarios the demo can run end-to-end on canned evidence ---
SCENARIOS = ("nav1_8", "tsc2", "lrrk2_pd", "scn2a_epilepsy", "gba1_pd", "c9orf72_als")

# --- disease routing: keyword -> (disease key, the auto-convened panel seating) ---
# Mirrors the routing table in ARCHITECTURE.md (one persona per lens, disease-matched).
DISEASE_ROUTES = {
    "pain": {
        "keys": ["pain", "nav1.8", "nav1_8", "scn10a", "scn11a", "nav1.9", "neuropathic", "analgesic", "nocicept"],
        "label": "neuropathic pain (peripheral sensory neuron)",
        "panel": [
            ("scientific", "Biotech CSO — ion channels (Xenon)"),
            ("commercial", "Pharma BD — CNS pain (Lundbeck)"),
            ("investability", "Venture GP — neuro (RA Capital)"),
            ("regulatory", "Pharma Neuro SVP / ex-FDA (Takeda Neuro)"),
        ],
    },
    "tsc": {
        "keys": ["tsc2", "tsc1", "tuberous", "mtor", "mtorc1", "rheb", "depdc5", "epilep", "fcd", "hyperexcitab"],
        "label": "tuberous sclerosis / mTORopathy CNS",
        "panel": [
            ("scientific", "Biotech CSO — CNS translational (Denali)"),
            ("commercial", "Pharma BD — rare disease (BioMarin)"),
            ("investability", "Venture GP — neuro (Third Rock)"),
            ("regulatory", "Pharma Neuro SVP / ex-FDA (Takeda Neuro)"),
        ],
    },
}
DISEASE_TO_SCENARIO = {"pain": "nav1_8", "tsc": "tsc2"}

# --- deliverable detection: keyword -> deliverable label ---
DELIVERABLE_RULES = [
    (["rank", "prioriti", "triage", "which target", "best target"], "a ranked, de-risked target list"),
    (["go/no-go", "go or no", "advance", "kill", "should we"], "a go / no-go call"),
    (["trial", "phase ", "endpoint", "ind ", "first-in-human", "fih"], "a trial-design assessment"),
    (["fund", "license", "deal", "invest", "acquire", "diligence"], "an investability / BD read"),
    (["franchise", "portfolio", "platform", "build a"], "a franchise / portfolio thesis"),
]

# --- dossier field groups (from dossier_schema.md) and when each is required ---
FIELD_GROUPS = {
    "A": "Target & mechanism",
    "B": "Scientific validation",
    "C": "Safety",
    "D": "Clinical & regulatory",
    "E": "Competitive, IP & commercial",
    "F": "Ecosystem / perception",
}


def _load_scenario(sid: str) -> dict:
    with open(os.path.join(SCENARIO_DIR, f"{sid}.json"), encoding="utf-8") as f:
        return json.load(f)


def _qmodels_catalog() -> list:
    with open(os.path.join(QMODELS_DIR, "catalog.json"), encoding="utf-8") as f:
        return json.load(f)["models"]


class Orchestrator:
    """The firm. Control flow is real; facts/verdicts come from providers."""

    # =========================================================================
    # CONTROL — Engagement Lead: triage -> scope -> plan  (live for ANY query)
    # =========================================================================
    def triage(self, query: str) -> dict:
        """Engagement Lead step 1: classify the prompt."""
        q = query.lower()
        disease = None
        for dk, route in DISEASE_ROUTES.items():
            if any(k in q for k in route["keys"]):
                disease = dk
                break
        deliverable = next((label for keys, label in DELIVERABLE_RULES if any(k in q for k in keys)),
                           "a ranked, de-risked target list")
        modality = ("ASO / genetic medicine" if any(k in q for k in ["aso", "antisense", "sirna", "degrader", "gene therapy"])
                    else "small molecule (default)")
        ptype = ("diligence" if "diligence" in q or "fund" in q or "license" in q
                 else "trial-design" if "trial" in q or "endpoint" in q
                 else "portfolio" if "portfolio" in q or "franchise" in q
                 else "prioritization")
        difficulty = "deep" if ptype in ("diligence", "portfolio") else "standard"
        # Capability-class: diligence (default) / design / experiment
        design_keys = ["design ", "engineer", "synthesize ", "build a ", "create a ",
                       "develop a ", "generate a ", "optimize a "]
        experiment_keys = ["test ", "validate ", "in vivo", "in vitro", "screen ",
                           "assay", "measure", "study "]
        if any(k in q for k in design_keys):
            cap_class = "design"
        elif any(k in q for k in experiment_keys):
            cap_class = "experiment"
        else:
            cap_class = "diligence"
        return {
            "type": ptype, "disease": disease,
            "disease_label": DISEASE_ROUTES[disease]["label"] if disease else "general CNS",
            "modality": modality, "deliverable": deliverable, "difficulty": difficulty,
            "class": cap_class,
        }

    def scope(self, triage: dict) -> dict:
        """Engagement Lead step 2: mark required vs skip dossier field groups."""
        t = triage["type"]
        required = ["A", "B", "C"]  # target, validation, safety — almost always
        if t in ("trial-design", "diligence"):
            required.append("D")
        if t in ("diligence", "portfolio"):
            required += ["E"]
        if t == "portfolio" or triage["difficulty"] == "deep":
            required.append("F")
        required = sorted(set(required))
        skip = [g for g in FIELD_GROUPS if g not in required]
        return {"required": required, "skip": skip}

    def _activated_agents(self, triage: dict, scope: dict) -> list:
        """Engagement Lead step 3: the minimal agent set, with a reason for each."""
        ags = [
            {"name": "Internal Science Lead", "why": "owns the moat hypothesis (the #N starting ranks)"},
            {"name": "EMET Analyst", "why": "biomedical evidence — genetics, pathway, drug-safety (live)"},
        ]
        if "B" in scope["required"]:
            ags.append({"name": "Q-Models Runner", "why": "quantify binding / selectivity / ADMET on the surfaced candidate"})
        if "C" in scope["required"]:
            ags.append({"name": "FDA Institutional Memory ⛔", "why": "dispositive-veto check on the class (prior CRL/withdrawal)"})
            ags.append({"name": "Post-Market Safety", "why": "class FAERS / label liabilities"})
        if "D" in scope["required"]:
            ags.append({"name": "Clinical-Trial Registry", "why": "trial precedent + amendment/termination signals"})
        if "E" in scope["required"]:
            ags.append({"name": "Patent & IP ⛔", "why": "freedom-to-operate veto check"})
            ags.append({"name": "Financial & Investor", "why": "competitive pipeline + deal comps"})
            ags.append({"name": "Payer & Market Access", "why": "reimbursement precedent"})
        if "F" in scope["required"]:
            ags.append({"name": "KOL & Social Signal", "why": "expert sentiment / pre-publication signal"})
        return ags

    def seat_panel(self, triage: dict, scenario: Optional[dict] = None) -> list:
        """Roundtable seating: one partner per relevant lens, disease-matched, + Red-Team."""
        dk = triage["disease"]
        seats = []
        route_panel = DISEASE_ROUTES[dk]["panel"] if dk else [
            ("scientific", "Biotech CSO (disease-matched)"),
            ("commercial", "Pharma BD SVP"),
            ("investability", "Venture GP"),
            ("regulatory", "Pharma Neuro SVP / ex-FDA"),
        ]
        # If a real scenario panel exists, name the actual personas; else the archetype.
        actual = {p["lens"]: p["persona"] for p in scenario["panel"]} if scenario else {}
        for lens, archetype in route_panel:
            seats.append({"lens": lens, "persona": actual.get(lens, archetype), "why": archetype})
        seats.append({"lens": "adversarial", "persona": "Adversarial Red-Team (always seated)",
                      "why": "institutional — must stay adversarial; stress every claim"})
        return seats

    def plan(self, query: str, scenario: Optional[dict] = None) -> dict:
        """Assemble the engagement plan (the first thing the user sees)."""
        tri = self.triage(query)
        sc = self.scope(tri)
        return {
            "deliverable": tri["deliverable"], "type": tri["type"],
            "disease": tri["disease_label"], "modality": tri["modality"],
            "class": tri.get("class", "diligence"),
            "required_fields": [f"{g} {FIELD_GROUPS[g]}" for g in sc["required"]],
            "skip_fields": [f"{g} {FIELD_GROUPS[g]}" for g in sc["skip"]],
            "agents": self._activated_agents(tri, sc),
            "panel": self.seat_panel(tri, scenario),
            "_triage": tri, "_scope": sc,
        }

    def plan_only(self, query: str) -> dict:
        """Front-facing planner for ANY query (no canned facts needed)."""
        return {"query": query, "plan": self.plan(query),
                "note": "Planner only — Bucket 1/2 require live agents (run via the /sapphire skill or a shipped scenario)."}

    # =========================================================================
    # BUCKET 1 — Research Manager: slot facts -> dossier, apply the rules
    # =========================================================================
    def bucket1(self, scenario: dict, scope: dict) -> dict:
        """Assemble + judge the fact dossier. Real Research-Manager logic over the evidence pack."""
        facts = scenario.get("facts", [])
        veto, divergence, known_unknowns = [], [], []
        for fct in facts:
            flag = fct.get("flag")
            if flag == "VETO":
                veto.append(fct["value"])
            elif flag == "DIVERGENCE":
                divergence.append(fct["value"])
            elif flag == "KNOWN_UNKNOWN":
                known_unknowns.append(fct["value"])
        # Completeness: which required field-groups have at least one fact?
        covered = {f["field"][0] for f in facts if f["field"][:1] in FIELD_GROUPS}
        missing = [f"{g} {FIELD_GROUPS[g]}" for g in scope["required"] if g not in covered]
        status = "complete" if not missing else "complete-with-known-unknowns"
        return {
            "source": scenario["discover"]["source"],
            "summary": scenario["discover"]["summary"],
            "result": scenario["discover"]["result"],
            "dossier": facts,
            "flags": {"VETO": veto, "DIVERGENCE": divergence, "KNOWN_UNKNOWNS": known_unknowns + missing},
            "status": status,
            # Research-Manager rule surfaced for transparency:
            "rules_applied": [
                "credibility-tier resolution (T1 regulatory > T2 curated > T3 press > T4 social)",
                "internal<->external DIVERGENCE surfaced, not reconciled",
                "VETO facts attached as gates for the roundtable, never silent kills",
            ],
        }

    # =========================================================================
    # VALIDATE — Q-Models Runner (facts: computed predictions)
    # =========================================================================
    def validate(self, scenario: dict) -> dict:
        v = dict(scenario["validate"])
        v["mock"] = True  # demo: shaped MOCK outputs; prod: AWS launch, same contract
        # canned scenario Q-Models outputs are shaped placeholders — stamp provenance honestly
        for r in v.get("runs", []):
            r.setdefault("provenance", "mock")
        return v

    # ---- Q-Models: the orchestrator can call any model (registry.json) ----
    def _qmodels(self):
        if getattr(self, "_qm", None) is None:
            import sys as _sys
            if HERE not in _sys.path:
                _sys.path.insert(0, HERE)
            from qmodels.client import QModelsClient
            self._qm = QModelsClient()
        return self._qm

    def call_model(self, tool_id: str, inputs: dict) -> dict:
        """Call any Q-Models tool by id. CPU tools → synchronous result row; GPU/batch tools → async
        job handle (poll with model_job_status). Every return carries provenance."""
        return self._qmodels().call(tool_id, inputs)

    def model_job_status(self, job_id: str) -> dict:
        return self._qmodels().poll(job_id)

    def tools_catalog(self) -> list:
        """Every callable Q-Models tool (id/label/task/tier/status) — the orchestrator's tool menu."""
        return [{"id": t.get("id"), "label": t.get("label") or t.get("name"), "task": t.get("task"),
                 "tier": t.get("tier"), "status": t.get("status")} for t in self._qmodels().tools()]

    # =========================================================================
    # BUCKET 2 — Roundtable Moderator: round 1 + round 2 + spread
    # =========================================================================
    def bucket2(self, scenario: dict) -> dict:
        panel = scenario["panel"]
        rebuttal = scenario.get("rebuttal", [])
        convictions = [p["conviction"] for p in panel]
        stances = [p["stance"] for p in panel]
        syn = scenario["synthesize"]
        spread = {
            "consensus": syn.get("consensus", ""),
            "dissent": syn.get("dissent", ""),
            "convergent_gate": syn.get("convergent_gate", ""),
            "conviction_range": f"{min(convictions)}-{max(convictions)} / 5" if convictions else "-",
            "stance_mix": {s: stances.count(s) for s in sorted(set(stances))},
            "moved_in_round2": [r["persona"].split(",")[0] for r in rebuttal if r.get("revised")],
        }
        return {"round1": panel, "round2": rebuttal, "spread": spread}

    # =========================================================================
    # SYNTHESIS — Engagement Lead final assembly
    # =========================================================================
    def synthesize(self, scenario: dict, bucket1: dict) -> dict:
        syn = dict(scenario["synthesize"])
        syn["open_items"] = bucket1["flags"]["KNOWN_UNKNOWNS"]
        return syn

    # =========================================================================
    # RUN — full end-to-end
    # =========================================================================
    def run(self, sid: str) -> dict:
        if sid not in SCENARIOS:
            raise ValueError(f"unknown scenario '{sid}'. Known: {SCENARIOS}. Use run_query() for free text.")
        sc = _load_scenario(sid)
        plan = self.plan(sc["query"], scenario=sc)
        b1 = self.bucket1(sc, plan["_scope"])
        val = self.validate(sc)
        b2 = self.bucket2(sc)
        syn = self.synthesize(sc, b1)
        return {
            "id": sc["id"], "title": sc["title"], "query": sc["query"], "headline": sc["headline"],
            "plan": {k: v for k, v in plan.items() if not k.startswith("_")},
            "discover": b1,        # Bucket 1: facts + dossier + flags + status
            "validate": val,       # Q-Models predictions
            "consult": b2,         # Bucket 2: round1 + round2 + spread
            "synthesize": syn,     # final recommendation
        }

    def run_query(self, query: str) -> dict:
        """Route a free-text query: to a shipped scenario if it matches, else plan-only."""
        tri = self.triage(query)
        sid = DISEASE_TO_SCENARIO.get(tri["disease"])
        if sid:
            run = self.run(sid)
            run["_routed_from_query"] = query
            return run
        return self.plan_only(query)


# A module-level singleton for convenience.
ENGINE = Orchestrator()
