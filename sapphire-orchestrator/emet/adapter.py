"""Map a raw EMET envelope (emet_protocol.md §7 / spec §3.1) to the harness `findings`
shape. EMET output is tiered T2 (curated/peer-reviewed); EMET corroborates/gates via cited
evidence and NEVER emits a formal VETO (that is the veto-class agents' T1 job)."""
from __future__ import annotations

PROVENANCE = "emet-live"


def normalize_emet(envelope: dict) -> dict:
    facts = []
    for ev in envelope.get("evidence", []) or []:
        src = (ev.get("source") or "").strip()
        idu = (ev.get("id_or_url") or "").strip()
        source = f"{src} [{idu}]".strip() if idu else src
        facts.append({"value": ev.get("claim", ""), "source": source, "tier": "T2"})

    verdict = envelope.get("verdict")
    notes = (envelope.get("notes") or "").strip()
    chat = envelope.get("chat_url", "")
    workflow = envelope.get("emet_workflow", "")
    if verdict == "flag":
        facts.append({"value": notes or f"EMET {workflow}: thin/contradictory evidence",
                      "source": chat, "tier": "T2", "flag": "KNOWN_UNKNOWN"})
    elif verdict == "no_go":
        facts.append({"value": notes or f"EMET {workflow}: contraindication / negative evidence",
                      "source": chat, "tier": "T2"})   # cited fact, NOT a VETO flag

    return {"candidate": envelope.get("candidate", ""), "facts": facts, "provenance": PROVENANCE}
