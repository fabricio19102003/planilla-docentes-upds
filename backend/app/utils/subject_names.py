"""Compare subject names written differently by designations and the curriculum.

"PROMOCIÓN DE LA SALUD I" and "Promoción de la Salud en el Ciclo de Vida I" are the same
subject: every word of the short name is a prefix of a word of the long one, ignoring
connectors, and roman numerals must match exactly (I is not II).
"""
from __future__ import annotations

import re
import unicodedata

_STOPWORDS = {"de", "la", "el", "en", "y", "e", "del", "los", "las"}
_NUMERALS = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}


def fold(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip()


def tokens(value: object) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", fold(value)) if token and token not in _STOPWORDS]


def token_match(short: list[str], long: list[str]) -> bool:
    if not short:
        return False
    if [t for t in short if t in _NUMERALS] != [t for t in long if t in _NUMERALS]:
        return False
    return all(any(word.startswith(token) for word in long if word not in _NUMERALS)
               for token in short if token not in _NUMERALS)


def same_subject(left: object, right: object) -> bool:
    if fold(left) == fold(right):
        return True
    a, b = tokens(left), tokens(right)
    return token_match(a, b) or token_match(b, a)
