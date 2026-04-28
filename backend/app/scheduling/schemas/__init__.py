"""Scheduling API schemas."""

from .academic_period import AcademicPeriodCreate, AcademicPeriodResponse
from .room import RoomCreate, RoomResponse, RoomTypeResponse
from .slot import ScheduledSlotDTO

__all__ = [
    "AcademicPeriodCreate",
    "AcademicPeriodResponse",
    "RoomCreate",
    "RoomResponse",
    "RoomTypeResponse",
    "ScheduledSlotDTO",
]
