"""Service layer for Group CRUD operations."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.scheduling.models.group import Group
from app.scheduling.models.shift import Shift
from app.scheduling.models.semester import Semester
from app.scheduling.models.academic_period import AcademicPeriod

logger = logging.getLogger(__name__)


class GroupService:
    """Group CRUD operations."""

    def _generate_code(self, shift: Shift, number: int, is_special: bool) -> str:
        """Generate group code from shift code + number, or 'G.E.' for special groups."""
        if is_special:
            return "G.E."
        return f"{shift.code}-{number}"

    def create_group(
        self,
        db: Session,
        *,
        academic_period_id: int,
        semester_id: int,
        shift_id: int,
        number: int,
        is_special: bool = False,
        student_count: int | None = None,
    ) -> Group:
        """Create a single group with auto-generated code."""
        # Validate FK references exist
        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == academic_period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail="Academic period not found")

        semester = db.query(Semester).filter(Semester.id == semester_id).first()
        if not semester:
            raise HTTPException(status_code=404, detail="Semester not found")

        shift = db.query(Shift).filter(Shift.id == shift_id).first()
        if not shift:
            raise HTTPException(status_code=404, detail="Shift not found")

        code = self._generate_code(shift, number, is_special)

        # Check unique constraint
        existing = (
            db.query(Group)
            .filter(
                Group.academic_period_id == academic_period_id,
                Group.semester_id == semester_id,
                Group.code == code,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Group '{code}' already exists for this period and semester",
            )

        group = Group(
            academic_period_id=academic_period_id,
            semester_id=semester_id,
            shift_id=shift_id,
            number=number,
            code=code,
            is_special=is_special,
            student_count=student_count,
        )
        db.add(group)
        db.flush()
        logger.info("Created group: %s (period=%d, semester=%d)", code, academic_period_id, semester_id)
        return group

    def create_bulk(
        self,
        db: Session,
        *,
        academic_period_id: int,
        semester_id: int,
        groups_data: list[dict[str, Any]],
    ) -> list[Group]:
        """Create multiple groups for a period+semester."""
        created: list[Group] = []
        for g in groups_data:
            group = self.create_group(
                db,
                academic_period_id=academic_period_id,
                semester_id=semester_id,
                shift_id=g["shift_id"],
                number=g["number"],
                is_special=g.get("is_special", False),
                student_count=g.get("student_count"),
            )
            created.append(group)
        return created

    def update(self, db: Session, group_id: int, **fields: Any) -> Group:
        """Update group fields (student_count, is_active)."""
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        for key, value in fields.items():
            if value is not None:
                setattr(group, key, value)
        db.flush()
        return group

    def delete(self, db: Session, group_id: int) -> dict[str, str]:
        """Delete a group. BR-GR-3: validates no designations reference this group (future check)."""
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail="Group not found")

        # BR-GR-3: future — check designations referencing this group
        # For now, just delete
        db.delete(group)
        db.flush()
        logger.info("Deleted group: %s (id=%d)", group.code, group.id)
        return {"detail": f"Group '{group.code}' deleted"}

    def list_by_period(
        self,
        db: Session,
        period_id: int,
        *,
        semester_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """List all groups for a period, optionally filtered by semester. Includes shift info."""
        query = (
            db.query(Group)
            .options(joinedload(Group.shift), joinedload(Group.semester))
            .filter(Group.academic_period_id == period_id)
        )
        if semester_id is not None:
            query = query.filter(Group.semester_id == semester_id)

        groups = query.order_by(Group.semester_id, Group.shift_id, Group.number).all()

        return [
            {
                "id": g.id,
                "academic_period_id": g.academic_period_id,
                "semester_id": g.semester_id,
                "semester_name": g.semester.name if g.semester else "",
                "shift_id": g.shift_id,
                "shift_code": g.shift.code if g.shift else "",
                "shift_name": g.shift.name if g.shift else "",
                "number": g.number,
                "code": g.code,
                "is_special": g.is_special,
                "student_count": g.student_count,
                "is_active": g.is_active,
            }
            for g in groups
        ]
