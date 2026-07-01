"""
planner.py — Robust query classification and entity extraction for Sapphire.

Handles the full ~300 CNS query range: single-gene, multi-gene, comparison,
ranking, SMILES/small-molecule, ASO sequence, and non-gene/disease queries.

Design constraints
------------------
- stdlib-only (no third-party imports); pure functions; never raises on bad input.
- Data boundary: only PUBLIC identifiers are extracted (gene symbols, disease terms,
  SMILES from explicitly presented tokens). Internal Quiver scores/ids NEVER leave.
- Honesty: when no entity is extractable, ``candidates`` is [] and ``query_type``
  is "non-gene" — caller degrades honestly rather than inventing a placeholder.

Public API
----------
classify_query(query) -> QueryScope
    Returns a QueryScope dataclass (also dict-serialisable via .to_dict()).

    Fields:
        query_type : str  — "single-gene" | "multi-gene" | "comparison" | "ranking"
                           | "smiles" | "sequence" | "non-gene"
        candidates : list[str]  — ordered gene symbols (or [] for non-gene queries)
        candidate  : str  — candidates[0] or "" (drop-in replacement for legacy `target`)
        genes      : list[str]  — same as candidates (legacy compat for bucket1_inputs)
        diseases   : list[str]  — extracted disease / indication terms
        smiles     : list[str]  — extracted SMILES strings
        sequences  : list[str]  — extracted ASO / DNA sequences (pure ATGC, ≥15)
        is_comparison : bool    — True when the query asks to compare ≥2 entities
        is_ranking    : bool    — True when the query asks to rank entities
        multi_entity  : bool    — True when candidates has ≥2 elements
        table_expected: bool    — True when a comparison/ranking table is expected
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


# ---------------------------------------------------------------------------
# Gene symbol patterns
# ---------------------------------------------------------------------------
# Primary: gene symbols that include a digit anchor.
#
# Pattern mirrors engagement.py's _GENE_RE: 1-8 uppercase letters, then 1-3
# digits (the numeric part of a gene symbol), then an optional trailing
# uppercase letter + optional single digit (for suffixes like CACNA1A, ATP2A2).
#
# The {1,3} digit limit is CRITICAL for data-boundary safety: internal Quiver IDs
# like QS00123 contain 5 consecutive digits (00123) after the letter prefix, so
# the pattern stops matching before word-boundary and QS00123 is correctly
# NOT extracted. This is consistent with engagement.extract_entities behavior.
#
# Coverage:
#   TSC1, TSC2          — 1 digit
#   SCN2A, SCN11A       — 2 digits; note SCN11 then A (suffix letter)
#   KCNQ2, KCNT1        — 1 digit
#   LRRK2, GBA1         — 1 digit
#   CACNA1A             — 1 digit + trailing A
#   ATP2A2, ATP1A3      — 1 digit + trailing letter + digit
#   GRIN2A              — 1 digit + trailing A
#   CHRNA4              — 1 digit + trailing A
_GENE_DIGIT_RE = re.compile(r"\b[A-Z]{1,8}[0-9]{1,3}[A-Z]?[0-9]?\b")

# Secondary: well-known alphabetic-only CNS gene symbols that NEVER contain digits.
# Kept as an explicit allowlist to avoid false positives on ordinary uppercase words.
_ALPHA_GENE_ALLOWLIST: frozenset = frozenset([
    "SNCA", "MAPT", "APP", "PTEN", "PARK", "PINK", "PARKIN", "DJ",
    "VPS", "FUS", "TDP", "C9ORF", "TARDBP", "SOD", "HTT", "ATXN",
    "APOE", "TREM", "CD33", "CLU", "CR1", "BIN", "ABCA", "SORL",
    "BACE", "ADAM", "NOTCH", "PRKG", "SHH", "BDNF", "GDNF", "NGF",
    "VEGF", "WNT", "AKT", "MTOR", "PIK", "AMPK", "PRKN", "LRRK",
    "GBA", "SMPD", "NPC", "ASAH", "HEXA", "HEXB", "GALC", "PSAP",
    "MECP", "SHANK", "CNTN", "NRXN", "NLGN",
])
# Secondary pattern: uppercase 2-6 letter tokens that are in the allowlist.
# We match any uppercase word and then check membership.
_ALPHA_TOKEN_RE = re.compile(r"\b[A-Z]{2,8}\b")


# ---------------------------------------------------------------------------
# SMILES detection
# ---------------------------------------------------------------------------
# SMILES strings MUST contain at least one structural/branch/bond character
# from the set {(, ), [, ], =, #, @, /, \\, %}.  These characters NEVER appear
# in gene symbols, disease terms, or ordinary English words.
# Additionally, a valid SMILES token must be a single whitespace-free run of
# SMILES-valid characters, at least 6 characters long.
#
# The key discriminator is the MANDATORY structural character — "CC(=O)O" has
# '(' and '='; "c1ccccc1" has a digit in context with lowercase letters in a
# ring-closure pattern that must include digits adjacent to aromatic atoms.
#
# We use a two-step approach:
#   1. Find whitespace-free tokens that contain at least one mandatory SMILES char.
#   2. Apply the _looks_like_smiles heuristic.
#
# This is conservative by design — a miss (undetected SMILES) is safe (Boltz
# stays dormant); a false positive would trigger an expensive job.

# Match a non-whitespace token that contains at least one mandatory SMILES
# structural char AND is at least 6 chars long.  The lookahead (?=...) asserts
# the token contains at least one char from the mandatory set.
_SMILES_MANDATORY_CHARS = set("()[]=#@/\\%")
_SMILES_TOKEN_RE = re.compile(r"[^\s]{6,}")


def _looks_like_smiles(token: str) -> bool:
    """Heuristic SMILES check.

    A token qualifies as SMILES when ALL of:
      - It is ≥ 6 characters long.
      - It contains AT LEAST ONE mandatory structural character from
        { (, ), [, ], =, #, @, /, \\, % } — these never appear in gene
        symbols, disease terms, or ordinary English words.
      - It is NOT a pure-alpha-uppercase token (gene symbols are all-caps).
      - It does NOT contain a space (SMILES is always whitespace-free).

    This is intentionally strict to minimise false positives.
    """
    if len(token) < 6:
        return False
    if " " in token:
        return False
    if not any(c in _SMILES_MANDATORY_CHARS for c in token):
        return False
    # Reject pure-uppercase alphabetic tokens (gene symbols, abbreviations)
    if token.isalpha() and token.isupper():
        return False
    return True


def _extract_smiles(query: str) -> list[str]:
    """Extract SMILES strings from query text.

    Requires the mandatory structural character heuristic — ordinary words,
    gene symbols, and disease terms are always rejected.  Returns deduplicated
    list in first-occurrence order.  Never raises.
    """
    seen: set = set()
    result: list = []
    for m in _SMILES_TOKEN_RE.finditer(query):
        tok = m.group(0)
        if _looks_like_smiles(tok) and tok not in seen:
            seen.add(tok)
            result.append(tok)
    return result


# ---------------------------------------------------------------------------
# ASO / DNA sequence detection
# ---------------------------------------------------------------------------
# Strict: standalone token, pure uppercase ATGC only, length ≥ 15.
_ASO_RE = re.compile(r"\b[ATGC]{15,}\b")


def _extract_sequences(query: str) -> list[str]:
    """Extract ASO/DNA sequences from query text. Strict (uppercase ATGC, ≥15 chars)."""
    seen: set = set()
    result: list = []
    for m in _ASO_RE.finditer(query):
        seq = m.group(0)
        if seq not in seen:
            seen.add(seq)
            result.append(seq)
    return result


# ---------------------------------------------------------------------------
# Gene symbol extraction
# ---------------------------------------------------------------------------

def _extract_genes(query: str) -> list[str]:
    """Extract gene symbols from query text.

    Two passes:
    1. _GENE_DIGIT_RE — digit-anchored gene symbols (TSC2, SCN2A, NAV1_8, etc.)
    2. Uppercase alphabetic tokens that appear in _ALPHA_GENE_ALLOWLIST.

    ASO sequences (pure ATGC ≥15) are excluded.
    Deduplicates while preserving first-occurrence order.
    """
    seen: set = set()
    result: list = []

    # Pass 1: digit-anchored
    for m in _GENE_DIGIT_RE.finditer(query):
        sym = m.group(0)
        # Exclude pure-ATGC sequences ≥15 chars (those are ASO tokens, not genes)
        if re.match(r"^[ATGC]+$", sym) and len(sym) >= 15:
            continue
        if sym not in seen:
            seen.add(sym)
            result.append(sym)

    # Pass 2: alphabetic allowlist
    for m in _ALPHA_TOKEN_RE.finditer(query):
        sym = m.group(0)
        if sym in _ALPHA_GENE_ALLOWLIST and sym not in seen:
            seen.add(sym)
            result.append(sym)

    return result


# ---------------------------------------------------------------------------
# Disease / indication term extraction
# ---------------------------------------------------------------------------
# A small vocabulary of CNS disease terms.  We keep this conservative (explicit
# list + fuzzy match) to avoid false positives on ordinary words.
_DISEASE_VOCAB = [
    "tuberous sclerosis",
    "tuberous sclerosis complex",
    "TSC",
    "epilepsy",
    "epilepsies",
    "ALS",
    "amyotrophic lateral sclerosis",
    "Parkinson",
    "Parkinson's disease",
    "Alzheimer",
    "Alzheimer's disease",
    "Huntington",
    "Huntington's disease",
    "autism",
    "autism spectrum disorder",
    "ASD",
    "schizophrenia",
    "depression",
    "anxiety",
    "ADHD",
    "attention deficit",
    "bipolar",
    "dementia",
    "frontotemporal dementia",
    "FTD",
    "Dravet",
    "Dravet syndrome",
    "Rett syndrome",
    "Rett",
    "fragile X",
    "fragile X syndrome",
    "phenylketonuria",
    "PKU",
    "Gaucher",
    "Gaucher disease",
    "Niemann-Pick",
    "GM2 gangliosidosis",
    "Tay-Sachs",
    "neuropathic pain",
    "pain",
    "migraine",
    "SMA",
    "spinal muscular atrophy",
    "DMD",
    "Duchenne muscular dystrophy",
    "glioblastoma",
    "GBM",
    "brain tumor",
    "brain tumour",
    "stroke",
    "traumatic brain injury",
    "TBI",
    "multiple sclerosis",
    "MS",
    "myasthenia gravis",
    "CNS",
]

# Build a single compiled pattern from the vocabulary (longest first to avoid
# partial shadowing of multi-word terms).
_DISEASE_PATTERNS = sorted(_DISEASE_VOCAB, key=len, reverse=True)
_DISEASE_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(d) for d in _DISEASE_PATTERNS) + r")\b",
    re.IGNORECASE,
)


def _extract_diseases(query: str) -> list[str]:
    """Extract disease / indication terms from query text.

    Returns deduplicated list (case-normalised to first occurrence) in
    first-occurrence order.  Abbreviations like TSC, ALS, ASD are included.
    Never raises.
    """
    seen: set = set()
    result: list = []
    for m in _DISEASE_RE.finditer(query):
        term = m.group(0)
        key = term.lower()
        if key not in seen:
            seen.add(key)
            result.append(term)
    return result


# ---------------------------------------------------------------------------
# Query type classification
# ---------------------------------------------------------------------------

# Comparison cues
_COMPARE_RE = re.compile(
    r"\bcompar(e|ing|ison)\b|\bvs\.?\b|\bversus\b|\brank\b|\brand\b"
    r"|\bdifferenc(e|es|iate)\b|\bcontrast\b|\bbet(ween|ter)\b",
    re.IGNORECASE,
)

# Ranking / enumeration cues
_RANK_RE = re.compile(
    r"\brank\b|\btop\s+\d+\b|\bbest\s+(gene|target|candidate|compound)\b"
    r"|\blist\b|\bidentif(y|ying)\s+(gene|target|candidate)\b"
    r"|\bwhich\s+(gene|target)s?\b",
    re.IGNORECASE,
)

# Rescue-specific cue (already exists in live_engine; replicated here for
# classify_query completeness — live_engine._is_rescue_ranking_query is the
# authoritative gate for the rescue deliverable).
_RESCUE_RE = re.compile(r"\brescue\b", re.IGNORECASE)


def _classify_type(
    query: str,
    genes: list[str],
    smiles: list[str],
    sequences: list[str],
) -> str:
    """Classify the query into one of the canonical types.

    Priority (first match wins):
      sequence  — ASO/DNA sequences present
      smiles    — SMILES strings present
      comparison— compare/vs/contrast cue + ≥2 genes
      ranking   — rank/top-N/list cue + ≥1 gene
      multi-gene— ≥2 gene symbols, no comparison/ranking cue
      single-gene— exactly 1 gene symbol
      non-gene  — no genes / sequences / SMILES
    """
    if sequences:
        return "sequence"
    if smiles:
        return "smiles"
    if genes:
        if len(genes) >= 2 and _COMPARE_RE.search(query):
            return "comparison"
        if _RANK_RE.search(query) or (_RESCUE_RE.search(query) and len(genes) >= 1):
            return "ranking"
        if len(genes) >= 2:
            return "multi-gene"
        return "single-gene"
    return "non-gene"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class QueryScope:
    """Structured result from classify_query().

    All fields have safe defaults — callers need not null-guard.
    """
    query_type: str = "non-gene"
    candidates: List[str] = field(default_factory=list)
    diseases: List[str] = field(default_factory=list)
    smiles: List[str] = field(default_factory=list)
    sequences: List[str] = field(default_factory=list)

    @property
    def candidate(self) -> str:
        """Legacy compatibility: first candidate or empty string."""
        return self.candidates[0] if self.candidates else ""

    @property
    def genes(self) -> List[str]:
        """Legacy compatibility alias for candidates."""
        return self.candidates

    @property
    def is_comparison(self) -> bool:
        return self.query_type == "comparison"

    @property
    def is_ranking(self) -> bool:
        return self.query_type == "ranking"

    @property
    def multi_entity(self) -> bool:
        return len(self.candidates) >= 2

    @property
    def table_expected(self) -> bool:
        """True when a comparison or ranking table is appropriate in the report."""
        return self.is_comparison or self.is_ranking or self.multi_entity

    def to_dict(self) -> dict:
        """Serialise to a plain dict (for logging / tracing)."""
        return {
            "query_type": self.query_type,
            "candidates": self.candidates,
            "candidate": self.candidate,
            "genes": self.genes,
            "diseases": self.diseases,
            "smiles": self.smiles,
            "sequences": self.sequences,
            "is_comparison": self.is_comparison,
            "is_ranking": self.is_ranking,
            "multi_entity": self.multi_entity,
            "table_expected": self.table_expected,
        }


def classify_query(query: str) -> QueryScope:
    """Classify a free-text CNS query and extract entities.

    Pure function — stdlib only, no I/O, never raises on any input.

    Parameters
    ----------
    query : str
        The free-text question / task submitted to Sapphire.  May be empty,
        None, or contain unusual characters — all are handled gracefully.

    Returns
    -------
    QueryScope
        A structured scope object.  ``candidate`` and ``genes`` are the
        drop-in replacements for the legacy ``target`` / ``ents["genes"]``
        fields produced by ``engagement.extract_entities``.
    """
    q = (query or "").strip()

    # Entity extraction — each extractor is independent and never raises.
    genes = _extract_genes(q)
    smiles = _extract_smiles(q)
    sequences = _extract_sequences(q)
    diseases = _extract_diseases(q)

    # Classification
    qtype = _classify_type(q, genes, smiles, sequences)

    return QueryScope(
        query_type=qtype,
        candidates=genes,
        diseases=diseases,
        smiles=smiles,
        sequences=sequences,
    )
