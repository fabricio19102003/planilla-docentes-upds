from datetime import datetime, time
from typing import Any, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, Time, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MedicineScheduleVersion(Base):
    __tablename__ = "medicine_schedule_versions"
    __table_args__ = (Index("uq_medicine_schedule_active_version", "is_active", unique=True,
                            postgresql_where=text("is_active = true"), sqlite_where=text("is_active = 1")),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    academic_period: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    workbook_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    source_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="preview", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    activated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)


class MedicineOffering(Base):
    __tablename__ = "medicine_offerings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("medicine_schedule_versions.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    semester: Mapped[Optional[int]] = mapped_column(Integer)
    subject_raw: Mapped[str] = mapped_column(String(300), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    group_code: Mapped[str] = mapped_column(String(50), nullable=False)
    shift: Mapped[Optional[str]] = mapped_column(String(50))
    source_sheet: Mapped[str] = mapped_column(String(200), nullable=False)
    source_row: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_payload: Mapped[Any] = mapped_column(JSON, nullable=False)


class MedicineMeeting(Base):
    __tablename__ = "medicine_meetings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offering_id: Mapped[int] = mapped_column(ForeignKey("medicine_offerings.id", ondelete="CASCADE"), index=True)
    activity: Mapped[str] = mapped_column(String(50), nullable=False)
    teacher_raw: Mapped[Optional[str]] = mapped_column(String(300))
    teacher_key: Mapped[Optional[str]] = mapped_column(String(300), index=True)
    day: Mapped[str] = mapped_column(String(20), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    source_cell: Mapped[str] = mapped_column(String(100), nullable=False)
    raw_payload: Mapped[Any] = mapped_column(JSON, nullable=False)


class MedicineImportIssue(Base):
    __tablename__ = "medicine_import_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("medicine_schedule_versions.id", ondelete="CASCADE"), index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[Any] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    accepted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)


class MedicineCorrection(Base):
    __tablename__ = "medicine_corrections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("medicine_schedule_versions.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    before_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    after_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)


class MedicineVersionEvent(Base):
    __tablename__ = "medicine_version_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("medicine_schedule_versions.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    details: Mapped[Any] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)


class MedicineSimulation(Base):
    __tablename__ = "medicine_simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("medicine_schedule_versions.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    inputs: Mapped[Any] = mapped_column(JSON, nullable=False)
    selected_result: Mapped[Any] = mapped_column(JSON, nullable=False)
    metrics: Mapped[Any] = mapped_column(JSON, nullable=False)
    warnings: Mapped[Any] = mapped_column(JSON, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    archived_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
