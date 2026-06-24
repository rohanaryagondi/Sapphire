import json
import sys
sys.stdout.reconfigure(encoding='utf-8')

NB_PATH = r"C:\Users\admin_robyn\Documents\Repositories\robyn_scs\plate_comparison.ipynb"

with open(NB_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

cells = nb["cells"]
print(f"Total cells: {len(cells)}")

# Check problematic cells
for i in [0, 1, 3, 5, 9, 14, 17, 18, 19, 20, 21, 22]:
    if i >= len(cells):
        print(f"\n=== Cell {i}: OUT OF RANGE ===")
        continue
    cell = cells[i]
    print(f"\n=== Cell {i} (type={cell['cell_type']}) ===")
    print("".join(cell["source"]))
