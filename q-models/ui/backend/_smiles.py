"""SMILES standardization — lifted verbatim from experiments/phase6_pgk2_fulleval.py:60.

The de-risking heads (BBBP/ClinTox) and DTI flip across valid encodings of the same
molecule (protonation/salt form), so we neutralize charges and strip salts to the
largest neutral fragment before scoring. Returns None on an unparseable SMILES.
"""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem.MolStandardize import rdMolStandardize


def neutral_parent(smi: str) -> str | None:
    """Standardize SMILES to neutral parent (strip salts, uncharge). None if invalid."""
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    mol = rdMolStandardize.LargestFragmentChooser().choose(mol)
    mol = rdMolStandardize.Uncharger().uncharge(mol)
    return Chem.MolToSmiles(mol)
