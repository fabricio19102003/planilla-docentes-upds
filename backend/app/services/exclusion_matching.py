"""Shared academic-scope matching for planilla exclusions."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _get_field(exclusion: Any, name: str) -> Any:
    if isinstance(exclusion, Mapping):
        return exclusion.get(name)
    return getattr(exclusion, name, None)


def exclusion_matches_designation(
    exclusion: Any,
    *,
    semester: Any,
    subject: Any,
    group_code: Any,
) -> bool:
    """Match one exclusion against one designation, including legacy subject scope."""
    scope = _get_field(exclusion, "scope")
    if scope == "global":
        return True
    if scope == "semester":
        return _get_field(exclusion, "semester_id") == semester
    if scope != "subject":
        return False
    if (
        _get_field(exclusion, "subject_id") != subject
        or _get_field(exclusion, "group_id") != group_code
    ):
        return False

    exclusion_semester = _get_field(exclusion, "semester_id")
    return exclusion_semester is None or exclusion_semester == semester
