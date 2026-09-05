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
from app.models.billing_publication import BillingPublication, BillingPublicationRevision
from app.models.notification import Notification
from app.models.outbound_notification_attempt import OutboundNotificationAttempt
from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.models.medicine_schedule import (
    MedicineCorrection, MedicineImportIssue, MedicineMeeting, MedicineOffering,
    MedicineScheduleVersion, MedicineSimulation, MedicineVersionEvent,
)

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
    "BillingPublicationRevision",
    "Notification",
    "OutboundNotificationAttempt",
    "ActivityLog",
    "AppSetting",
    "PracticeAttendanceLog",
    "PracticePlanillaOutput",
    "MedicineScheduleVersion",
    "MedicineOffering",
    "MedicineMeeting",
    "MedicineImportIssue",
    "MedicineCorrection",
    "MedicineVersionEvent",
    "MedicineSimulation",
]

from app.models.whatsapp_preference import WhatsAppPreference
from app.models.billing_notification import (
    BillingMediaToken,
    BillingNotificationBatch,
    BillingNotificationJob,
    BillingNotificationCapacityReservation,
    BillingNotificationCapacityWindow,
    WhatsAppEvent,
)

__all__ += [
    "WhatsAppPreference",
    "BillingNotificationBatch",
    "BillingNotificationJob",
    "BillingNotificationCapacityReservation",
    "BillingNotificationCapacityWindow",
    "WhatsAppEvent",
    "BillingMediaToken",
]
