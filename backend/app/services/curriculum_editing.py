"""Edit the current curriculum plan (student-portal S11). Flushes, never commits; callers log and commit.

Changes apply to the plan every student follows. Removing a subject from the plan never touches the
students' history: records point at catalog subjects, not at curriculum slots.
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.academic_management import SubjectOffering
from app.models.academic_records import CurriculumPlan, CurriculumSubject
from app.services import academic_records_service


def get_plan(db: Session, plan_id: int) -> CurriculumPlan:
    plan = db.get(CurriculumPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan de estudio no encontrado")
    return plan


def get_slot(plan: CurriculumPlan, slot_id: int) -> CurriculumSubject:
    slot = next((slot for slot in plan.subjects if slot.id == slot_id), None)
    if slot is None:
        raise HTTPException(status_code=404, detail="Materia no encontrada en la malla")
    return slot


def slot_values(slot: CurriculumSubject) -> dict[str, Any]:
    return {
        "semester": slot.semester, "name": slot.slot_name, "code": slot.subject.code if slot.subject else None,
        "theory_hours": slot.theory_hours, "practice_hours": slot.practice_hours, "credits": slot.credits,
        "is_elective": slot.is_elective,
    }


def _semester_slots(plan: CurriculumPlan, semester: int, without: Optional[CurriculumSubject] = None):
    return sorted((s for s in plan.subjects if s.semester == semester and s is not without), key=lambda s: s.position)


def _renumber(plan: CurriculumPlan, semester: int) -> None:
    for position, slot in enumerate(_semester_slots(plan, semester)):
        slot.position = position


def _validate(plan: CurriculumPlan, values: dict[str, Any], slot: Optional[CurriculumSubject] = None) -> None:
    if values["semester"] > plan.total_semesters:
        raise HTTPException(status_code=422, detail=f"La malla tiene {plan.total_semesters} semestres")
    if not values["code"] and not values["is_elective"]:
        raise HTTPException(status_code=422, detail="Una materia que no es electiva necesita sigla")
    if values["theory_hours"] == 0 and values["practice_hours"] == 0:
        raise HTTPException(status_code=422, detail="La materia necesita al menos una hora teórica o práctica")
    if values["code"] and any(
        other.subject and other.subject.code == values["code"] and other is not slot for other in plan.subjects
    ):
        raise HTTPException(status_code=409, detail=f"{values['code']} ya está en la malla")


def _apply(db: Session, slot: CurriculumSubject, values: dict[str, Any]) -> None:
    subject = None
    if values["code"]:
        subject, created = academic_records_service.get_or_create_subject(db, values["code"], values["name"])
        # Renaming in the curriculum is an explicit decision, so the catalog subject follows it.
        if not created and subject.name != values["name"]:
            subject.name = values["name"]
    slot.subject_id = subject.id if subject else None
    slot.subject = subject
    slot.slot_name = values["name"]
    slot.theory_hours = values["theory_hours"]
    slot.practice_hours = values["practice_hours"]
    slot.credits = values["credits"]
    slot.is_elective = values["is_elective"]


def add_slot(db: Session, plan: CurriculumPlan, values: dict[str, Any]) -> CurriculumSubject:
    _validate(plan, values)
    slot = CurriculumSubject(plan_id=plan.id, semester=values["semester"],
                             position=len(_semester_slots(plan, values["semester"])))
    _apply(db, slot, values)
    plan.subjects.append(slot)
    db.flush()
    return slot


def update_slot(db: Session, plan: CurriculumPlan, slot: CurriculumSubject, values: dict[str, Any]) -> None:
    _validate(plan, values, slot)
    previous_semester = slot.semester
    if values["semester"] != previous_semester:
        slot.semester = values["semester"]
        slot.position = len(_semester_slots(plan, values["semester"], without=slot))
    _apply(db, slot, values)
    _renumber(plan, previous_semester)
    db.flush()


def remove_slot(db: Session, plan: CurriculumPlan, slot: CurriculumSubject) -> None:
    plan.subjects.remove(slot)
    db.delete(slot)
    _renumber(plan, slot.semester)
    db.flush()


def reorder(db: Session, plan: CurriculumPlan, semester: int, slot_ids: list[int]) -> None:
    slots = _semester_slots(plan, semester)
    if sorted(slot_ids) != sorted(s.id for s in slots) or len(set(slot_ids)) != len(slot_ids):
        raise HTTPException(status_code=422, detail="El orden debe incluir todas las materias del semestre")
    by_id = {s.id: s for s in slots}
    for position, slot_id in enumerate(slot_ids):
        by_id[slot_id].position = position
    db.flush()


def add_semester(db: Session, plan: CurriculumPlan) -> None:
    plan.total_semesters += 1
    db.flush()


def remove_semester(db: Session, plan: CurriculumPlan, semester: int) -> None:
    if semester != plan.total_semesters or semester <= 1 or _semester_slots(plan, semester):
        raise HTTPException(status_code=409, detail="Solo se puede quitar el último semestre y tiene que estar vacío")
    plan.total_semesters -= 1
    db.flush()


def generate_offerings(db: Session, plan: CurriculumPlan, academic_period: str) -> dict[str, Any]:
    """Create the period's subject offerings from the plan; existing ones (and their manual edits) stay."""
    existing = {
        (offering.subject_id, offering.semester)
        for offering in db.query(SubjectOffering).filter(
            SubjectOffering.program_id == plan.program_id, SubjectOffering.academic_period == academic_period,
        )
    }
    created, kept, skipped = [], [], []
    for slot in sorted(plan.subjects, key=lambda s: (s.semester, s.position)):
        if slot.subject is None:
            skipped.append({"name": slot.slot_name, "semester": slot.semester, "reason": "Electiva sin materia asignada"})
            continue
        if slot.theory_hours == 0 and slot.practice_hours == 0:
            skipped.append({"name": slot.slot_name, "semester": slot.semester, "reason": "Sin horas en la malla"})
            continue
        if (slot.subject_id, slot.semester) in existing:
            kept.append(slot.subject.code)
            continue
        db.add(SubjectOffering(
            subject_id=slot.subject_id, program_id=plan.program_id, academic_period=academic_period,
            semester=slot.semester, theory_hours=slot.theory_hours, practice_hours=slot.practice_hours, active=True,
        ))
        created.append(slot.subject.code)
    db.flush()
    return {"academic_period": academic_period, "created": created, "existing": kept, "skipped": skipped}
