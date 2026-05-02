"""Service layer for Semester CRUD."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.scheduling.models.semester import Semester
from app.scheduling.models.subject import Subject


class SemesterService:
    """Semester CRUD operations."""

    def create(self, db: Session, *, career_id: int, number: int, name: str) -> Semester:
        # Check uniqueness
        existing = (
            db.query(Semester)
            .filter(Semester.career_id == career_id, Semester.number == number)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Semester {number} already exists for this career",
            )
        semester = Semester(career_id=career_id, number=number, name=name.strip())
        db.add(semester)
        db.flush()
        return semester

    def update(self, db: Session, semester_id: int, **fields: Any) -> Semester:
        semester = db.query(Semester).filter(Semester.id == semester_id).first()
        if not semester:
            raise HTTPException(status_code=404, detail="Semester not found")
        for key, value in fields.items():
            if value is not None:
                setattr(semester, key, value)
        db.flush()
        return semester

    def list_by_career(self, db: Session, career_id: int) -> list[dict[str, Any]]:
        semesters = (
            db.query(Semester)
            .options(joinedload(Semester.subjects))
            .filter(Semester.career_id == career_id)
            .order_by(Semester.number)
            .all()
        )
        return [
            {
                "id": s.id,
                "career_id": s.career_id,
                "number": s.number,
                "name": s.name,
                "is_active": s.is_active,
                "subject_count": len(s.subjects),
            }
            for s in semesters
        ]

    def get(self, db: Session, semester_id: int) -> dict[str, Any]:
        semester = (
            db.query(Semester)
            .options(joinedload(Semester.subjects))
            .filter(Semester.id == semester_id)
            .first()
        )
        if not semester:
            raise HTTPException(status_code=404, detail="Semester not found")
        return {
            "id": semester.id,
            "career_id": semester.career_id,
            "number": semester.number,
            "name": semester.name,
            "is_active": semester.is_active,
            "subject_count": len(semester.subjects),
            "subjects": [
                {
                    "id": subj.id,
                    "semester_id": subj.semester_id,
                    "code": subj.code,
                    "name": subj.name,
                    "theoretical_hours": subj.theoretical_hours,
                    "practical_hours": subj.practical_hours,
                    "credits": subj.credits,
                    "is_elective": subj.is_elective,
                    "is_active": subj.is_active,
                }
                for subj in semester.subjects
            ],
        }

    def delete(self, db: Session, semester_id: int) -> dict[str, str]:
        semester = db.query(Semester).filter(Semester.id == semester_id).first()
        if not semester:
            raise HTTPException(status_code=404, detail="Semester not found")
        # Check no active subjects with designations reference this semester
        # For now, just check if it has subjects — future: check designations
        active_subjects = (
            db.query(Subject)
            .filter(Subject.semester_id == semester_id, Subject.is_active.is_(True))
            .count()
        )
        if active_subjects > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot delete semester with {active_subjects} active subjects. "
                       "Deactivate or remove subjects first.",
            )
        db.delete(semester)
        db.flush()
        return {"detail": "Semester deleted"}
