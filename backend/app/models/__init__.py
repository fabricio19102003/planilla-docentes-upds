# Import all models to ensure they are registered in Base.metadata
# This is CRITICAL — SQLAlchemy needs all models imported before create_all() is called
from app.models.teacher import Teacher
from app.models.designation import Designation
from app.models.biometric import BiometricUpload, BiometricRecord
from app.models.attendance import AttendanceRecord
from app.models.planilla import PlanillaOutput
from app.models.user import User
from app.models.detail_request import DetailRequest
from app.models.report import Report
from app.models.billing_publication import BillingPublication
from app.models.notification import Notification

__all__ = [
    "Teacher",
    "Designation",
    "BiometricUpload",
    "BiometricRecord",
    "AttendanceRecord",
    "PlanillaOutput",
    "User",
    "DetailRequest",
    "Report",
    "BillingPublication",
    "Notification",
]
