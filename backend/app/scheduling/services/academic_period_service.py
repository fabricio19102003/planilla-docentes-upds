from datetime import date
from sqlalchemy.orm import Session
from typing import Optional
from app.scheduling.models.academic_period import AcademicPeriod


class AcademicPeriodService:
    VALID_STATUSES = {"planning", "active", "closed"}

    @staticmethod
    def parse_code(code: str) -> tuple[int, int]:
        normalized = code.strip().upper()
        if "/" not in normalized:
            raise ValueError("AcademicPeriod code must be in the form I/2026 or II/2026")

        semester_token, year_token = normalized.split("/", 1)
        if semester_token not in {"I", "II"}:
            raise ValueError("AcademicPeriod code must start with I or II")

        try:
            year = int(year_token)
        except ValueError as exc:
            raise ValueError("AcademicPeriod code must include a valid year") from exc

        semester_number = 1 if semester_token == "I" else 2
        return semester_number, year

    @staticmethod
    def get_active_period(db: Session) -> Optional[AcademicPeriod]:
        return (
            db.query(AcademicPeriod)
            .filter(AcademicPeriod.is_active.is_(True))
            .order_by(AcademicPeriod.id.desc())
            .first()
        )

    @staticmethod
    def get_period_by_code(db: Session, code: str) -> Optional[AcademicPeriod]:
        return db.query(AcademicPeriod).filter(AcademicPeriod.code == code.strip().upper()).first()

    @staticmethod
    def create_period(
        db: Session,
        code: str,
        name: str,
        start_date: date,
        end_date: date,
        status: str = "planning",
        is_active: bool = False,
    ) -> AcademicPeriod:
        if status not in AcademicPeriodService.VALID_STATUSES:
            raise ValueError(f"Invalid period status: {status}")
        if start_date >= end_date:
            raise ValueError("AcademicPeriod start_date must be before end_date")

        semester_number, year = AcademicPeriodService.parse_code(code)
        period = AcademicPeriod(
            code=code.strip().upper(),
            name=name.strip(),
            year=year,
            semester_number=semester_number,
            start_date=start_date,
            end_date=end_date,
            status=status,
            is_active=is_active,
        )
        db.add(period)
        db.flush()

        if is_active:
            AcademicPeriodService.activate_period(db=db, period_id=period.id)

        return period

    @staticmethod
    def activate_period(db: Session, period_id: int) -> AcademicPeriod:
        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
        if period is None:
            raise ValueError("AcademicPeriod not found")

        if period.status == "closed":
            raise ValueError("Cannot activate a closed academic period")

        current = AcademicPeriodService.get_active_period(db)
        if current and current.id != period.id:
            current.is_active = False

        period.is_active = True
        if period.status == "planning":
            period.status = "active"

        db.flush()
        return period

    @staticmethod
    def get_or_create_by_code(db: Session, code: str) -> AcademicPeriod:
        existing = AcademicPeriodService.get_period_by_code(db, code)
        if existing:
            return existing

        semester_number, year = AcademicPeriodService.parse_code(code)
        period = AcademicPeriod(
            code=code.strip().upper(),
            name=code.strip(),
            year=year,
            semester_number=semester_number,
            start_date=date.today(),
            end_date=date.today(),
            status="planning",
            is_active=False,
        )
        db.add(period)
        db.flush()
        return period
