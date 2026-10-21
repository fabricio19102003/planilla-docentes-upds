"""Semester values as integers.

Designations store the semester as a Spanish ordinal ("PRIMERO", "Séptimo");
the academic module stores an integer. Both must compare equal.
"""
from __future__ import annotations

import unicodedata

_ORDINALS = {
    "PRIMERO": 1, "SEGUNDO": 2, "TERCERO": 3, "CUARTO": 4, "QUINTO": 5,
    "SEXTO": 6, "SEPTIMO": 7, "OCTAVO": 8, "NOVENO": 9, "DECIMO": 10,
}


def semester_number(value: object) -> int | None:
    """Return the semester as 1..N, or None when it is not recognizable."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = unicodedata.normalize("NFKD", str(value or "").strip().upper())
    text = "".join(char for char in text if not unicodedata.combining(char))
    if text.isdigit():
        return int(text) or None
    return _ORDINALS.get(text)
