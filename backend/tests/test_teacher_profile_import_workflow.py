from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.teacher import TeacherCreate, TeacherUpdate


def test_three_teacher_types_are_canonical_and_unknown_is_rejected():
    for value in ("EXTERNO", "PERMANENTE", "TITULAR", "titular"):
        assert TeacherCreate(ci="1", full_name="Synthetic", external_permanent=value).external_permanent == value.upper()
        assert TeacherUpdate(external_permanent=value).external_permanent == value.upper()
    with pytest.raises(ValidationError):
        TeacherCreate(ci="1", full_name="Synthetic", external_permanent="SERVICIOS PROFESIONALES")
