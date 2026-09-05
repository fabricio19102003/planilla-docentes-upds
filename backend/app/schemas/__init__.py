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
    DesignationContractDatesUpdate,
    DesignationResponse,
    DesignationImportApplyResponse,
    DesignationImportCounts,
    DesignationImportPreviewResponse,
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
    "DesignationContractDatesUpdate",
    "DesignationResponse",
    "DesignationImportApplyResponse",
    "DesignationImportCounts",
    "DesignationImportPreviewResponse",
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

from app.schemas.billing_notification import (
    BillingMediaTokenResponse,
    BillingNotificationBatchResponse,
    BillingNotificationJobResponse,
    WhatsAppEventResponse,
    WhatsAppPreferenceResponse,
)

__all__ += [
    "WhatsAppPreferenceResponse",
    "BillingNotificationBatchResponse",
    "BillingNotificationJobResponse",
    "WhatsAppEventResponse",
    "BillingMediaTokenResponse",
]
