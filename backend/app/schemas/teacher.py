from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.designation import DesignationResponse


class TeacherBase(BaseModel):
    ci: str
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    external_permanent: Optional[str] = None
    academic_level: Optional[str] = None
    profession: Optional[str] = None
    specialty: Optional[str] = None
    bank: Optional[str] = None
    account_number: Optional[str] = None
    sap_code: Optional[str] = None
    invoice_retention: Optional[str] = None


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    gender: Optional[str] = None
    external_permanent: Optional[str] = None
    academic_level: Optional[str] = None
    profession: Optional[str] = None
    specialty: Optional[str] = None
    bank: Optional[str] = None
    account_number: Optional[str] = None
    sap_code: Optional[str] = None
    invoice_retention: Optional[str] = None


class TeacherResponse(TeacherBase):
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class TeacherWithDesignations(TeacherResponse):
    designations: list[DesignationResponse] = []

    model_config = ConfigDict(from_attributes=True)
