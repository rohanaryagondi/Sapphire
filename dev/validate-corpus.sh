#!/usr/bin/env bash
# dev/validate-corpus.sh <corpus-dir>
#
# Mechanical citation-integrity gate for a Bucket-1 agent knowledge corpus
# (sapphire-orchestrator/corpus/<agent>/). Run it before any corpus PR — and the
# corpus build METHOD requires it to pass. Born from the FDA-memory pilot audit,
# which found real facts but leaky citations (a 404 URL, quotes not in their source,
# a T1 tier on a press-wire). This makes those failure modes mechanical, not trust-based.
#
# Two ingestion sources, both verified here (see corpus METHOD.md Step 3):
#   - Browser pass  → FDA-primary, tier T1 (must be on a primary .gov/.edu/PMC domain).
#   - EMET pass     → biomedical class-grounding, tier T2, source "EMET (BenchSci)",
#                     url = pubmed.ncbi.nlm.nih.gov/<pmid>/ (resolves 2xx), plus additive
#                     "provenance"/"emet_chat_url" fields. EMET cards conform as-is: the
#                     invariant-field check below is a SUBSET test (inv - set(c)), so the
#                     extra fields never trip it, and T2 is exempt from the T1-domain rule.
#                     Do NOT weaken these checks to admit EMET cards — they already pass.
#
# Checks index.jsonl, per card:
#   1. valid JSON; invariant fields present (claim, date, source, url, quote, tier);
#      tier in {T1,T2}; quote <= 60 words. (Extra fields beyond the invariant set are allowed.)
#   2. tier T1 ONLY if the url host is a primary/authoritative domain: US *.gov / *.edu /
#      PMC / NCBI, OR a credentialed ex-US national drug regulator (EMA, MHRA/gov.uk, PMDA,
#      Health Canada, TGA, Swissmedic, NMPA — see PRIMARY_REGULATOR). HTA/reimbursement
#      bodies (NICE, PBAC, G-BA, ICER) and press stay T2. Else the card must be T2.
#   3. every url resolves: HTTP 2xx/3xx = ok; 4xx (dead/wrong, e.g. 404) = HARD FAIL;
#      403/429/000 (blocked/timeout) = ok ONLY if the card sets "unverifiable_by_fetch": true,
#      else a HARD FAIL (forces honest tagging instead of a silently-unfetched URL).
#
# NOTE on quote fidelity: a full substring-match check needs the fetched source text,
# which many primary domains (fda.gov/federalregister.gov) block. That check stays a
# METHOD discipline (Step 4) + the adversarial review; this script enforces what is
# mechanically decidable. Quote length IS checked here.
#
# Exit: 0 clean, 1 if any HARD FAIL.
set -uo pipefail

DIR="${1:?usage: validate-corpus.sh <corpus-dir>}"
IDX="$DIR/index.jsonl"
[ -f "$IDX" ] || { echo "✗ no index.jsonl in $DIR"; exit 1; }

# 1 + 2: schema / tier-domain (Python; no network).
python3 - "$IDX" <<'PY'
import json, sys
from urllib.parse import urlparse
idx = sys.argv[1]
inv = {"claim","date","source","url","quote","tier"}
# US primary domains (suffix match).
PRIMARY_SUFFIX = (".gov", ".edu")
PRIMARY_HOST = ("pmc.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov")
# Credentialed ex-US NATIONAL DRUG REGULATORS — primary regulatory sources, T1-eligible
# (their domains aren't .gov so the US suffix rule misses them). HTA/reimbursement bodies
# (NICE, PBAC, G-BA, ICER, CDA-AMC) are NOT here — they stay T2 per the agent specs. A card
# is T1 if its host equals or is a subdomain of one of these. (Added 2026-06-24 for
# global-regulatory-divergence; also serves policy-legislative & other ex-US-primary agents.)
PRIMARY_REGULATOR = (
    "ema.europa.eu",      # European Medicines Agency
    "gov.uk",             # MHRA (UK)
    "pmda.go.jp",         # PMDA (Japan)
    "canada.ca", "hc-sc.gc.ca",  # Health Canada
    "tga.gov.au",         # TGA (Australia)
    "swissmedic.ch",      # Swissmedic
    "nmpa.gov.cn",        # NMPA (China)
)
fails = []
rows = []
for i, line in enumerate(open(idx, encoding="utf-8"), 1):
    line = line.strip()
    if not line:
        continue
    try:
        c = json.loads(line)
    except Exception as e:
        fails.append(f"line {i}: bad JSON ({e})"); continue
    rows.append((i, c))
    miss = inv - set(c)
    if miss: fails.append(f"line {i}: missing fields {sorted(miss)}")
    if c.get("tier") not in ("T1", "T2"): fails.append(f"line {i}: tier must be T1|T2 (got {c.get('tier')!r})")
    if len(str(c.get("quote","")).split()) > 60: fails.append(f"line {i}: quote >60 words")
    host = urlparse(str(c.get("url",""))).netloc.lower()
    if c.get("tier") == "T1":
        ok = (host.endswith(PRIMARY_SUFFIX)
              or host in PRIMARY_HOST
              or any(host == d or host.endswith("." + d) for d in PRIMARY_REGULATOR))
        if not ok: fails.append(f"line {i}: tier T1 but non-primary host '{host}' "
                                f"(T1 = US .gov/.edu/PMC/NCBI or a credentialed national regulator; HTA/press = T2)")
# stash the url list for the bash url-check phase
with open("/tmp/_corpus_urls.txt","w") as f:
    for i,c in rows:
        f.write(f"{i}\t{c.get('url','')}\t{1 if c.get('unverifiable_by_fetch') else 0}\n")
print(f"  cards parsed: {len(rows)}")
if fails:
    print("  SCHEMA/TIER FAILURES:")
    for m in fails: print("   ✗", m)
    sys.exit(1)
print("  ✓ schema + tier-domain ok")
PY
schema_rc=$?
[ "$schema_rc" -ne 0 ] && { echo "✗ corpus validation FAILED (schema/tier)"; exit 1; }

# 3: URL liveness (network; best-effort, deterministic on 4xx).
echo "  checking URL liveness…"
url_fail=0
while IFS=$'\t' read -r ln url unverif; do
  [ -z "$url" ] && continue
  code="$(curl -sS -o /dev/null -L --max-time 20 -w '%{http_code}' "$url" 2>/dev/null || echo 000)"
  case "$code" in
    2*|3*) : ;;  # resolves
    401|403|429)  # page exists but blocks automation (e.g. fda.gov) — rescuable by an honest flag
        if [ "$unverif" = "1" ]; then echo "   • line $ln: HTTP $code blocked — tagged unverifiable_by_fetch (ok)";
        else echo "   ✗ line $ln: HTTP $code blocked and NOT tagged unverifiable_by_fetch — $url"; url_fail=1; fi ;;
    4*) echo "   ✗ line $ln: HTTP $code (dead/wrong URL — repoint it) $url"; url_fail=1 ;;  # 404/410/etc = dead, never rescuable
    *)  # 000 timeout / 5xx — treat like a block: rescuable by the flag
        if [ "$unverif" = "1" ]; then echo "   • line $ln: HTTP $code timeout/5xx — tagged unverifiable_by_fetch (ok)";
        else echo "   ✗ line $ln: HTTP $code timeout/5xx and NOT tagged unverifiable_by_fetch — $url"; url_fail=1; fi ;;
  esac
done < /tmp/_corpus_urls.txt
rm -f /tmp/_corpus_urls.txt

if [ "$url_fail" -ne 0 ]; then echo "✗ corpus validation FAILED (URL integrity)"; exit 1; fi
echo "✓ corpus validation CLEAN: $DIR"
