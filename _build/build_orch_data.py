# -*- coding: utf-8 -*-
"""Bundle sapphire-orchestrator scenarios + Q-Models catalog into site/orchestrator_data.js."""
import json, os
ROOT = r"C:\Users\rohan.gondi\Desktop\Sapphire\sapphire-capability-map"
ORCH = os.path.join(ROOT, "sapphire-orchestrator")
OUT  = os.path.join(ROOT, "site", "orchestrator_data.js")

scenarios = []
for sid in ("nav1_8", "tsc2"):
    with open(os.path.join(ORCH, "scenarios", f"{sid}.json"), encoding="utf-8") as f:
        scenarios.append(json.load(f))
with open(os.path.join(ORCH, "qmodels", "catalog.json"), encoding="utf-8") as f:
    catalog = json.load(f)["models"]

data = {"scenarios": scenarios, "catalog": catalog}
with open(OUT, "w", encoding="utf-8") as f:
    f.write("// Auto-generated from sapphire-orchestrator/ by _build/build_orch_data.py\n")
    f.write("window.SAPPHIRE_ORCH = ")
    json.dump(data, f, ensure_ascii=False, indent=2)
    f.write(";\n")
print("wrote", OUT, "| scenarios:", len(scenarios), "| catalog:", len(catalog))
