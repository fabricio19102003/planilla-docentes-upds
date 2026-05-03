from app.scheduling.schemas.career import (
    CareerCreate,
    CareerUpdate,
    CareerResponse,
    CareerWithSemesters,
    CurriculumImportRequest,
    CurriculumImportResponse,
)
from app.scheduling.schemas.semester import (
    SemesterCreate,
    SemesterUpdate,
    SemesterResponse,
    SemesterWithSubjects,
)
from app.scheduling.schemas.subject import (
    SubjectCreate,
    SubjectUpdate,
    SubjectResponse,
)
from app.scheduling.schemas.academic_period import (
    AcademicPeriodCreate,
    AcademicPeriodUpdate,
    AcademicPeriodResponse,
)
from app.scheduling.schemas.shift import (
    ShiftUpdate,
    ShiftResponse,
)
from app.scheduling.schemas.group import (
    GroupCreate,
    GroupBulkCreate,
    GroupUpdate,
    GroupResponse,
)
from app.scheduling.schemas.slot import (
    SlotCreate,
    SlotUpdate,
    SlotResponse,
    SlotValidateRequest,
    RoomAssignRequest,
    ConflictResponse,
)
from app.scheduling.schemas.availability import (
    AvailabilitySlotInput,
    SetAvailabilityRequest,
    AvailabilitySlotResponse,
    TeacherAvailabilityResponse,
)
from app.scheduling.schemas.room import (
    RoomTypeCreate,
    RoomTypeUpdate,
    RoomTypeResponse,
    EquipmentCreate,
    EquipmentUpdate,
    EquipmentResponse,
    RoomCreate,
    RoomUpdate,
    RoomResponse,
    RoomEquipmentCreate,
    RoomEquipmentResponse,
)

__all__ = [
    "CareerCreate",
    "CareerUpdate",
    "CareerResponse",
    "CareerWithSemesters",
    "CurriculumImportRequest",
    "CurriculumImportResponse",
    "SemesterCreate",
    "SemesterUpdate",
    "SemesterResponse",
    "SemesterWithSubjects",
    "SubjectCreate",
    "SubjectUpdate",
    "SubjectResponse",
    "AcademicPeriodCreate",
    "AcademicPeriodUpdate",
    "AcademicPeriodResponse",
    "ShiftUpdate",
    "ShiftResponse",
    "GroupCreate",
    "GroupBulkCreate",
    "GroupUpdate",
    "GroupResponse",
    "RoomTypeCreate",
    "RoomTypeUpdate",
    "RoomTypeResponse",
    "EquipmentCreate",
    "EquipmentUpdate",
    "EquipmentResponse",
    "RoomCreate",
    "RoomUpdate",
    "RoomResponse",
    "RoomEquipmentCreate",
    "RoomEquipmentResponse",
    "SlotCreate",
    "SlotUpdate",
    "SlotResponse",
    "SlotValidateRequest",
    "RoomAssignRequest",
    "ConflictResponse",
    "AvailabilitySlotInput",
    "SetAvailabilityRequest",
    "AvailabilitySlotResponse",
    "TeacherAvailabilityResponse",
]
