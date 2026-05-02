"""Service layer for Subject CRUD."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.scheduling.models.subject import Subject
from app.scheduling.models.semester import Semester


class SubjectService:
    """Subject CRUD operations."""

    def create(self, db: Session, *, semester_id: int, code: str | None = None,
               name: str, theoretical_hours: int = 0, practical_hours: int = 0,
               credits: int = 0, is_elective: bool = False) -> Subject:
        # Verify semester exists
        semester = db.query(Semester).filter(Semester.id == semester_id).first()
        if not semester:
            raise HTTPException(status_code=404, detail="Semester not found")

        # Check code uniqueness if provided
        if code:
            existing = db.query(Subject).filter(Subject.code == code).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Subject with code '{code}' already exists",
                )

        subject = Subject(
            semester_id=semester_id,
            code=code.strip() if code else None,
            name=name.strip(),
            theoretical_hours=theoretical_hours,
            practical_hours=practical_hours,
            credits=credits,
            is_elective=is_elective,
        )
        db.add(subject)
        db.flush()
        return subject

    def update(self, db: Session, subject_id: int, **fields: Any) -> Subject:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        for key, value in fields.items():
            if value is not None:
                setattr(subject, key, value)
        db.flush()
        return subject

    def get(self, db: Session, subject_id: int) -> Subject:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        return subject

    def list_by_semester(self, db: Session, semester_id: int) -> list[Subject]:
        return (
            db.query(Subject)
            .filter(Subject.semester_id == semester_id)
            .order_by(Subject.code)
            .all()
        )

    def search(self, db: Session, query: str, career_id: int | None = None) -> list[Subject]:
        """Search subjects by name or code. Optionally filter by career."""
        q = db.query(Subject).filter(
            or_(
                Subject.name.ilike(f"%{query}%"),
                Subject.code.ilike(f"%{query}%"),
            )
        )
        if career_id is not None:
            q = q.join(Semester).filter(Semester.career_id == career_id)
        return q.order_by(Subject.name).limit(50).all()

    def delete(self, db: Session, subject_id: int) -> dict[str, str]:
        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")
        # Future: check no active designations reference this subject
        db.delete(subject)
        db.flush()
        return {"detail": "Subject deleted"}
