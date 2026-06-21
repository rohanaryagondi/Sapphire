#!/usr/bin/env bash
# Download every MAMMAL checkpoint this project uses into ./models/.
#
# Why a script (not `huggingface-cli download`): on the network this project was built on,
# the HF downloader's resume is broken. We list each repo's files via the HF API and curl
# them with resume (-C -) + retry. Skips the giant *.ckpt files (the safetensors is enough;
# wdr91/pgk2 ship a redundant 4.6 GB last.ckpt we don't need).
#
# Total: ~17 GB across 10 checkpoints (each is the full 458M model + a task head). M-series Mac
# or any Linux box is fine. Re-runnable: completed files are skipped/resumed.
#
# Usage:
#   bash scripts/download_models.sh            # all 10
#   bash scripts/download_models.sh base_458m moleculenet_bbbp   # just these
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p models

# local_dir : huggingface_repo_id
read -r -d '' MAP <<'EOF' || true
base_458m                ibm-research/biomed.omics.bl.sm.ma-ted-458m
dti_bindingdb_pkd        ibm-research/biomed.omics.bl.sm.ma-ted-458m.dti_bindingdb_pkd
dti_bindingdb_pkd_peer   ibm-research/biomed.omics.bl.sm.ma-ted-458m.dti_bindingdb_pkd_peer
moleculenet_bbbp         ibm-research/biomed.omics.bl.sm.ma-ted-458m.moleculenet_bbbp
moleculenet_clintox_tox  ibm-research/biomed.omics.bl.sm.ma-ted-458m.moleculenet_clintox_tox
moleculenet_clintox_fda  ibm-research/biomed.omics.bl.sm.ma-ted-458m.moleculenet_clintox_fda
protein_solubility       ibm-research/biomed.omics.bl.sm.ma-ted-458m.protein_solubility
tcr_epitope_bind         ibm-research/biomed.omics.bl.sm.ma-ted-458m.tcr_epitope_bind
wdr91_asms               michalozeryflato/biomed.omics.bl.sm.ma-ted-458m.wdr91_asms
pgk2_del_cdd             michalozeryflato/biomed.omics.bl.sm.ma-ted-458m.pgk2_del_cdd
EOF

want_filter=("$@")
wanted() { [ ${#want_filter[@]} -eq 0 ] && return 0; for w in "${want_filter[@]}"; do [ "$w" = "$1" ] && return 0; done; return 1; }

dl() {  # dl <url> <out>
  curl -fL -C - --retry 20 --retry-delay 3 --speed-limit 5000 --speed-time 30 -o "$2" "$1"
}

while read -r dir repo; do
  [ -z "${dir:-}" ] && continue
  wanted "$dir" || continue
  echo "=== $dir  <-  $repo ==="
  mkdir -p "models/$dir"
  # list files in the repo (skip *.ckpt); preserves tokenizer/ subpaths
  files=$(curl -fsSL "https://huggingface.co/api/models/$repo" \
          | python3 -c "import json,sys;print('\n'.join(s['rfilename'] for s in json.load(sys.stdin).get('siblings',[]) if not s['rfilename'].endswith('.ckpt') and s['rfilename']!='.gitattributes'))")
  for f in $files; do
    out="models/$dir/$f"
    mkdir -p "$(dirname "$out")"
    if [ -s "$out" ]; then echo "  have $f"; continue; fi
    echo "  get  $f"
    dl "https://huggingface.co/$repo/resolve/main/$f" "$out"
  done
done <<< "$MAP"

echo ""
echo "Done. Sanity check:"
for d in models/*/; do
  [ -f "${d}model.safetensors" ] && echo "  OK   ${d}" || echo "  MISS ${d} (no model.safetensors)"
done
