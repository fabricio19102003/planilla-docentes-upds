from sqlalchemy import String, Integer, DateTime, Date, Time, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, date, time
from typing import Optional

from app.database import Base


class BiometricUpload(Base):
    __tablename__ = "biometric_uploads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    upload_date: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_teachers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="uploaded", nullable=False
    )  # uploaded, processing, completed, error

    # Relationships
    records: Mapped[list["BiometricRecord"]] = relationship(
        "BiometricRecord", back_populates="upload", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BiometricUpload id={self.id} filename={self.filename} {self.month}/{self.year}>"


class BiometricRecord(Base):
    __tablename__ = "biometric_records"

    __table_args__ = (
        UniqueConstraint("upload_id", "teacher_ci", "date", "entry_time", name="uq_biometric_record"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("biometric_uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    teacher_ci: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    teacher_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    entry_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    exit_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    worked_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shift: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), nullable=False)

    # Relationships
    upload: Mapped["BiometricUpload"] = relationship("BiometricUpload", back_populates="records")
    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(  # noqa: F821
        "AttendanceRecord", back_populates="biometric_record"
    )

    def __repr__(self) -> str:
        return f"<BiometricRecord ci={self.teacher_ci} date={self.date} entry={self.entry_time}>"
