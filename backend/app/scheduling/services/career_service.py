"""Service layer for Career CRUD and curriculum import."""

from __future__ import annotations

import logging
import unicodedata
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.scheduling.models.career import Career
from app.scheduling.models.semester import Semester
from app.scheduling.models.subject import Subject
from app.scheduling.schemas.career import (
    CurriculumImportRequest,
    CurriculumImportResponse,
)

logger = logging.getLogger(__name__)

# Ordinal name helpers for semesters
_ORDINALS = {
    1: "1er", 2: "2do", 3: "3er", 4: "4to", 5: "5to",
    6: "6to", 7: "7mo", 8: "8vo", 9: "9no", 10: "10mo",
    11: "11vo", 12: "12vo", 13: "13vo", 14: "14vo",
}


def _semester_name(number: int) -> str:
    ordinal = _ORDINALS.get(number, f"{number}vo")
    return f"{ordinal} Semestre"


def _generate_code(name: str) -> str:
    """Generate a career code from the name (first 3 uppercase letters, ASCII)."""
    # Strip accents and take first 3 alpha chars
    normalized = unicodedata.normalize("NFD", name)
    letters = [c for c in normalized if unicodedata.category(c) != "Mn" and c.isalpha()]
    return "".join(letters[:3]).upper()


class CareerService:
    """Career CRUD operations and curriculum import."""

    # --- CRUD ---

    def create(self, db: Session, *, code: str, name: str, description: str | None = None) -> Career:
        existing = db.query(Career).filter(Career.code == code).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Career with code '{code}' already exists",
            )
        career = Career(code=code.upper().strip(), name=name.strip(), description=description)
        db.add(career)
        db.flush()
        return career

    def update(self, db: Session, career_id: int, **fields: Any) -> Career:
        career = db.query(Career).filter(Career.id == career_id).first()
        if not career:
            raise HTTPException(status_code=404, detail="Career not found")
        for key, value in fields.items():
            if value is not None:
                setattr(career, key, value)
        db.flush()
        return career

    def deactivate(self, db: Session, career_id: int) -> Career:
        return self.update(db, career_id, is_active=False)

    def reactivate(self, db: Session, career_id: int) -> Career:
        return self.update(db, career_id, is_active=True)

    def list_all(self, db: Session, *, active_only: bool = True) -> list[dict[str, Any]]:
        query = db.query(Career).options(
            joinedload(Career.semesters).joinedload(Semester.subjects)
        )
        if active_only:
            query = query.filter(Career.is_active.is_(True))
        query = query.order_by(Career.name)
        careers = query.all()

        results = []
        for c in careers:
            subject_count = sum(len(s.subjects) for s in c.semesters)
            results.append({
                "id": c.id,
                "code": c.code,
                "name": c.name,
                "description": c.description,
                "is_active": c.is_active,
                "semester_count": len(c.semesters),
                "subject_count": subject_count,
            })
        return results

    def get(self, db: Session, career_id: int) -> dict[str, Any]:
        career = (
            db.query(Career)
            .options(joinedload(Career.semesters).joinedload(Semester.subjects))
            .filter(Career.id == career_id)
            .first()
        )
        if not career:
            raise HTTPException(status_code=404, detail="Career not found")

        semesters_data = []
        total_subjects = 0
        for s in career.semesters:
            subjects_data = [
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
                for subj in s.subjects
            ]
            total_subjects += len(subjects_data)
            semesters_data.append({
                "id": s.id,
                "career_id": s.career_id,
                "number": s.number,
                "name": s.name,
                "is_active": s.is_active,
                "subject_count": len(subjects_data),
                "subjects": subjects_data,
            })

        return {
            "id": career.id,
            "code": career.code,
            "name": career.name,
            "description": career.description,
            "is_active": career.is_active,
            "semester_count": len(semesters_data),
            "subject_count": total_subjects,
            "semesters": semesters_data,
        }

    # --- Curriculum Import ---

    def import_curriculum(
        self,
        db: Session,
        curriculum: CurriculumImportRequest,
    ) -> CurriculumImportResponse:
        """Import malla curricular JSON. Creates or updates career, semesters, subjects."""
        warnings: list[str] = []

        # 1. Find or create career
        career_name = curriculum.carrera.strip()
        code = _generate_code(career_name)

        # First try by name (most reliable — avoids code collisions like
        # "Medicina" and "Medio Ambiente" both generating "MED")
        career = db.query(Career).filter(Career.name == career_name).first()
        if not career:
            # Then try by code, but verify the name matches
            career_by_code = db.query(Career).filter(Career.code == code).first()
            if career_by_code:
                if career_by_code.name.strip().lower() == career_name.lower():
                    career = career_by_code
                else:
                    # Code collision: different career with same generated code
                    # Generate a disambiguated code
                    suffix = 2
                    while db.query(Career).filter(Career.code == f"{code}{suffix}").first():
                        suffix += 1
                    code = f"{code}{suffix}"
                    warnings.append(
                        f"Código '{_generate_code(career_name)}' ya existe para otra carrera "
                        f"('{career_by_code.name}'). Se usó código alternativo: '{code}'"
                    )

        if career:
            logger.info("Found existing career: %s (%s)", career.name, career.code)
        else:
            career = Career(code=code, name=career_name)
            db.add(career)
            db.flush()
            logger.info("Created career: %s (%s)", career.name, career.code)

        semesters_created = 0
        semesters_existing = 0
        subjects_created = 0
        subjects_updated = 0

        # 2. Process semesters
        for sem_data in curriculum.semestres:
            semester = (
                db.query(Semester)
                .filter(Semester.career_id == career.id, Semester.number == sem_data.semestre)
                .first()
            )
            if semester:
                semesters_existing += 1
            else:
                semester = Semester(
                    career_id=career.id,
                    number=sem_data.semestre,
                    name=_semester_name(sem_data.semestre),
                )
                db.add(semester)
                db.flush()
                semesters_created += 1
                logger.info("Created semester %d for %s", sem_data.semestre, career.code)

            # 3. Process subjects
            for subj_data in sem_data.materias:
                subj_name = subj_data.nombre.strip()
                subj_code = subj_data.codigo.strip() if subj_data.codigo else None

                # CR is already coerced to int by the Pydantic validator
                cr_value = subj_data.CR

                is_elective = subj_code is None

                existing_subject: Subject | None = None
                if subj_code:
                    existing_subject = (
                        db.query(Subject).filter(Subject.code == subj_code).first()
                    )
                else:
                    # For electives (no code), match by semester + name
                    existing_subject = (
                        db.query(Subject)
                        .filter(Subject.semester_id == semester.id, Subject.name == subj_name)
                        .first()
                    )

                if existing_subject:
                    # Update if changed
                    changed = False
                    if existing_subject.name != subj_name:
                        existing_subject.name = subj_name
                        changed = True
                    if existing_subject.theoretical_hours != subj_data.HT:
                        existing_subject.theoretical_hours = subj_data.HT
                        changed = True
                    if existing_subject.practical_hours != subj_data.HP:
                        existing_subject.practical_hours = subj_data.HP
                        changed = True
                    if existing_subject.credits != cr_value:
                        existing_subject.credits = cr_value
                        changed = True
                    if existing_subject.semester_id != semester.id:
                        existing_subject.semester_id = semester.id
                        changed = True
                    if existing_subject.is_elective != is_elective:
                        existing_subject.is_elective = is_elective
                        changed = True
                    if changed:
                        subjects_updated += 1
                else:
                    subject = Subject(
                        semester_id=semester.id,
                        code=subj_code,
                        name=subj_name,
                        theoretical_hours=subj_data.HT,
                        practical_hours=subj_data.HP,
                        credits=cr_value,
                        is_elective=is_elective,
                    )
                    db.add(subject)
                    subjects_created += 1

            db.flush()

        return CurriculumImportResponse(
            career_id=career.id,
            career_code=career.code,
            semesters_created=semesters_created,
            semesters_existing=semesters_existing,
            subjects_created=subjects_created,
            subjects_updated=subjects_updated,
            warnings=warnings,
        )
