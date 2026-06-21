"""DrugCLIP pocket prep for the Quiver cross-modal eval (Nav1.8 + mTOR).

DrugCLIP (NeurIPS 2023, MIT) is pocket<->molecule CLIP: it embeds a protein BINDING-SITE
POCKET (3D atom coords) and a molecule (SMILES + 3D conformer) into a shared space and ranks
by cosine. Unlike BALM (sequence-only), it needs a defined 3D pocket — which for our data-poor
targets (no holo crystal) is a judgment call. This script prepares the pocket inputs.

Two pocket-definition modes (pick one; see the plan in the chat / scorecard):
  --mode fpocket   : run fpocket on the AlphaFold model, take the top-ranked pocket (unbiased,
                     but may not be the pharmacologically relevant site for a big channel).
  --mode residues  : carve the pocket from a literature binding-site residue list (Nav1.8
                     local-anesthetic site in DIV-S6; mTOR FRB domain for rapalogs) — biased
                     toward the right site but requires the residue numbers to be correct vs
                     the AlphaFold numbering.

Output: per target, a pocket PDB + the atom coordinates DrugCLIP's Uni-Mol pocket encoder wants
(packed into pocket.lmdb on the instance by the eval step). Structures: AlphaFold DB.

Targets:
  Nav1.8  SCN10A  UniProt Q9Y5Y9   (AF-Q9Y5Y9-F1)
  mTOR            UniProt P42345   (AF-P42345-F1)   [large; AF splits into fragments]
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

TARGETS = {
    "nav18": {"uniprot": "Q9Y5Y9", "name": "Nav1.8 (SCN10A)",
              # local-anesthetic / pore-blocker site, domain IV S6 (approx; verify vs AF numbering)
              "site_residues": [1399, 1400, 1401, 1402, 1403, 1404, 1405, 1406]},
    "mtor": {"uniprot": "P42345", "name": "mTOR",
             # FRB domain (rapamycin/FKBP12 site) ~residues 2025-2114; rapalogs bind here
             "site_residues": list(range(2025, 2115, 10))},
}
RADIUS = 10.0  # Angstroms around the site/pocket center


def fetch_alphafold_pdb(uniprot: str, out: Path) -> Path:
    # Ask the AlphaFold API for the current pdbUrl (the static version bumps: v4->v6...),
    # then fall back to trying explicit versions newest-first.
    url = None
    try:
        meta = json.loads(urllib.request.urlopen(
            f"https://alphafold.ebi.ac.uk/api/prediction/{uniprot}", timeout=60).read())
        if meta:
            url = meta[0].get("pdbUrl")
    except Exception as e:
        print(f"[warn] AF API lookup failed for {uniprot}: {e}", flush=True)
    candidates = [url] if url else []
    candidates += [f"https://alphafold.ebi.ac.uk/files/AF-{uniprot}-F1-model_{v}.pdb"
                   for v in ("v6", "v5", "v4")]
    for u in candidates:
        if not u:
            continue
        try:
            print(f"[fetch] {u}", flush=True)
            out.write_bytes(urllib.request.urlopen(u, timeout=120).read())
            return out
        except Exception as e:
            print(f"[warn] fetch failed {u}: {e}", flush=True)
    raise RuntimeError(f"could not fetch AlphaFold PDB for {uniprot}")


def parse_ca_coords(pdb_text: str) -> dict[int, tuple]:
    """resnum -> CA (x,y,z) from a PDB string (chain A)."""
    coords = {}
    for line in pdb_text.splitlines():
        if line.startswith("ATOM") and line[12:16].strip() == "CA":
            try:
                resnum = int(line[22:26]); x = float(line[30:38]); y = float(line[38:46]); z = float(line[46:54])
                coords[resnum] = (x, y, z)
            except ValueError:
                continue
    return coords


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["fpocket", "residues"], default="residues")
    ap.add_argument("--out", default="/opt/drugclip_pockets")
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)

    manifest = {}
    for key, t in TARGETS.items():
        pdb = fetch_alphafold_pdb(t["uniprot"], out / f"{key}.pdb")
        text = pdb.read_text()
        ca = parse_ca_coords(text)
        info = {"uniprot": t["uniprot"], "name": t["name"], "pdb": str(pdb),
                "n_residues": len(ca), "mode": args.mode}
        if args.mode == "residues":
            present = [r for r in t["site_residues"] if r in ca]
            info["site_residues_present"] = present
            info["site_residues_missing"] = [r for r in t["site_residues"] if r not in ca]
            if present:
                xs = [ca[r][0] for r in present]; ys = [ca[r][1] for r in present]; zs = [ca[r][2] for r in present]
                info["pocket_center"] = [round(sum(xs)/len(xs), 2), round(sum(ys)/len(ys), 2), round(sum(zs)/len(zs), 2)]
            info["radius"] = RADIUS
            info["note"] = ("pocket = atoms within RADIUS of the literature site-residue centroid; "
                            "VERIFY residue numbers match AlphaFold numbering before trusting")
        else:
            info["note"] = "run fpocket on the PDB on-instance; take top-ranked pocket (fpocket not bundled here)"
        manifest[key] = info
        print(f"[{key}] {t['name']}: {len(ca)} residues, mode={args.mode}", flush=True)

    (out / "pocket_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[done] wrote {out/'pocket_manifest.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
