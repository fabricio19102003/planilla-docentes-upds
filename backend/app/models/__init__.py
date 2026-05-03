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
from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.practice_planilla import PracticePlanillaOutput
from app.scheduling.models.career import Career
from app.scheduling.models.semester import Semester
from app.scheduling.models.subject import Subject
from app.scheduling.models.academic_period import AcademicPeriod
from app.scheduling.models.shift import Shift
from app.scheduling.models.group import Group
from app.scheduling.models.room_type import RoomType
from app.scheduling.models.equipment import Equipment
from app.scheduling.models.room import Room
from app.scheduling.models.room_equipment import RoomEquipment

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
    "ActivityLog",
    "AppSetting",
    "PracticeAttendanceLog",
    "PracticePlanillaOutput",
    "Career",
    "Semester",
    "Subject",
    "AcademicPeriod",
    "Shift",
    "Group",
    "RoomType",
    "Equipment",
    "Room",
    "RoomEquipment",
]
