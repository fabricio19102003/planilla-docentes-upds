from app.schemas.teacher import TeacherBase, TeacherCreate, TeacherUpdate, TeacherResponse, TeacherWithDesignations
from app.schemas.designation import DesignationBase, DesignationCreate, DesignationResponse
from app.schemas.biometric import BiometricUploadResponse, BiometricRecordBase, BiometricRecordResponse, BiometricUploadCreate
from app.schemas.attendance import AttendanceRecordBase, AttendanceRecordResponse, AttendanceWithDetails, AttendanceSummary
from app.schemas.planilla import PlanillaOutputResponse, PlanillaGenerateRequest, PlanillaGenerateResponse

# Resolve forward references for schemas with circular dependencies
TeacherWithDesignations.model_rebuild()

__all__ = [
    "TeacherBase",
    "TeacherCreate",
    "TeacherUpdate",
    "TeacherResponse",
    "TeacherWithDesignations",
    "DesignationBase",
    "DesignationCreate",
    "DesignationResponse",
    "BiometricUploadResponse",
    "BiometricRecordBase",
    "BiometricRecordResponse",
    "BiometricUploadCreate",
    "AttendanceRecordBase",
    "AttendanceRecordResponse",
    "AttendanceWithDetails",
    "AttendanceSummary",
    "PlanillaOutputResponse",
    "PlanillaGenerateRequest",
    "PlanillaGenerateResponse",
]
