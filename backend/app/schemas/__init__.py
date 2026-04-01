from app.schemas.teacher import (
    TeacherBase,
    TeacherCreate,
    TeacherUpdate,
    TeacherResponse,
    TeacherWithDesignations,
    TeacherAttendanceSummary,
    PaginatedTeachersResponse,
    TeacherDetailResponse,
)
from app.schemas.designation import (
    DesignationBase,
    DesignationCreate,
    DesignationResponse,
    DesignationUploadResponse,
)
from app.schemas.biometric import (
    BiometricUploadResponse,
    BiometricRecordBase,
    BiometricRecordResponse,
    BiometricUploadCreate,
    BiometricUploadResult,
)
from app.schemas.attendance import (
    AttendanceRecordBase,
    AttendanceRecordResponse,
    AttendanceWithDetails,
    AttendanceSummary,
    AttendanceProcessRequest,
    AttendanceProcessResponse,
    PaginatedAttendanceResponse,
    ObservationResponse,
    MonthlyAttendanceSummaryResponse,
)
from app.schemas.planilla import (
    PlanillaOutputResponse,
    PlanillaGenerateRequest,
    PlanillaGenerateResponse,
    DashboardSummaryResponse,
)

# Resolve forward references for schemas with circular dependencies
TeacherWithDesignations.model_rebuild()
TeacherDetailResponse.model_rebuild()

__all__ = [
    "TeacherBase",
    "TeacherCreate",
    "TeacherUpdate",
    "TeacherResponse",
    "TeacherWithDesignations",
    "TeacherAttendanceSummary",
    "PaginatedTeachersResponse",
    "TeacherDetailResponse",
    "DesignationBase",
    "DesignationCreate",
    "DesignationResponse",
    "DesignationUploadResponse",
    "BiometricUploadResponse",
    "BiometricRecordBase",
    "BiometricRecordResponse",
    "BiometricUploadCreate",
    "BiometricUploadResult",
    "AttendanceRecordBase",
    "AttendanceRecordResponse",
    "AttendanceWithDetails",
    "AttendanceSummary",
    "AttendanceProcessRequest",
    "AttendanceProcessResponse",
    "PaginatedAttendanceResponse",
    "ObservationResponse",
    "MonthlyAttendanceSummaryResponse",
    "PlanillaOutputResponse",
    "PlanillaGenerateRequest",
    "PlanillaGenerateResponse",
    "DashboardSummaryResponse",
]
