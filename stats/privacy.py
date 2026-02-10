"""Operator privacy / anonymization."""

import os
from .contest_data import QSO


def anonymize(operators: list[str]) -> tuple[dict[str, str], list[str]]:
    """Create anonymization mapping.

    Returns (mapping_dict, anonymized_list) where mapping_dict maps
    real callsign -> "Op1", "Op2", etc.
    """
    mapping = {}
    anon_list = []
    for i, op in enumerate(sorted(operators), start=1):
        label = f"Op{i}"
        mapping[op] = label
        anon_list.append(label)
    return mapping, anon_list


def apply_privacy(qsos: list[QSO], mapping: dict[str, str]):
    """Replace operator field in all QSOs using the mapping."""
    for qso in qsos:
        if qso.operator in mapping:
            qso.operator = mapping[qso.operator]


def write_operator_key(mapping: dict[str, str], output_dir: str):
    """Write the real-to-anonymous mapping to a text file."""
    path = os.path.join(output_dir, "operator_key.txt")
    with open(path, 'w') as f:
        f.write("Operator Key (keep private)\n")
        f.write("=" * 30 + "\n")
        for real, anon in sorted(mapping.items(), key=lambda x: x[1]):
            f.write(f"{anon} = {real}\n")
