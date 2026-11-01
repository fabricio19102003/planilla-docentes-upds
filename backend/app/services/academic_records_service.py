"""Curriculum loading and read models for academic records."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.academic_management import AcademicProgram, AcademicSubject
from app.models.academic_records import CurriculumPlan, CurriculumSubject

DEFAULT_CURRICULUM_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "curricula" / "medicina-510-01.json"
)


def _get_or_create_program(db: Session, code: str, name: str) -> AcademicProgram:
    program = db.query(AcademicProgram).filter(AcademicProgram.code == code).one_or_none()
    if program is None:
        program = AcademicProgram(code=code, name=name, active=True)
        db.add(program)
        db.flush()
    return program


def get_or_create_subject(db: Session, code: str, name: str) -> tuple[AcademicSubject, bool]:
    """Return the catalog subject for ``code``; existing subjects are never renamed."""
    subject = db.query(AcademicSubject).filter(AcademicSubject.code == code).one_or_none()
    if subject is not None:
        return subject, False
    subject = AcademicSubject(code=code, name=name, active=True)
    db.add(subject)
    db.flush()
    return subject, True


def load_curriculum(db: Session, payload: dict[str, Any]) -> CurriculumPlan:
    """Create or update one curriculum plan from its JSON definition. Flushes, never commits."""
    program = _get_or_create_program(db, payload["program_code"], payload["program_name"])
    semesters = payload["semesters"]
    plan = (
        db.query(CurriculumPlan)
        .filter(CurriculumPlan.program_id == program.id, CurriculumPlan.code == payload["plan_code"])
        .one_or_none()
    )
    if plan is None:
        plan = CurriculumPlan(
            program_id=program.id, code=payload["plan_code"], name=payload["plan_name"],
            total_semesters=len(semesters), active=True,
        )
        db.add(plan)
        db.flush()
    else:
        plan.name = payload["plan_name"]
        plan.total_semesters = len(semesters)

    existing = {(slot.semester, slot.slot_name): slot for slot in plan.subjects}
    for semester in semesters:
        for position, item in enumerate(semester["subjects"]):
            subject_id = None
            if item["code"]:
                subject_id = get_or_create_subject(db, item["code"], item["name"])[0].id
            slot = existing.get((semester["semester"], item["name"]))
            if slot is None:
                slot = CurriculumSubject(plan_id=plan.id, semester=semester["semester"], slot_name=item["name"])
                db.add(slot)
            slot.subject_id = subject_id
            slot.position = position
            slot.theory_hours = item["theory_hours"]
            slot.practice_hours = item["practice_hours"]
            slot.credits = item["credits"]
            slot.is_elective = item["code"] is None
    db.flush()
    db.refresh(plan)
    return plan


def load_default_curriculum(db: Session) -> CurriculumPlan:
    payload = json.loads(DEFAULT_CURRICULUM_PATH.read_text(encoding="utf-8"))
    return load_curriculum(db, payload)


def serialize_plan(plan: CurriculumPlan) -> dict[str, Any]:
    semesters: dict[int, list[dict[str, Any]]] = {}
    for slot in sorted(plan.subjects, key=lambda item: (item.semester, item.position)):
        semesters.setdefault(slot.semester, []).append({
            "id": slot.id,
            "subject_id": slot.subject_id,
            "code": slot.subject.code if slot.subject else None,
            "name": slot.slot_name,
            "theory_hours": slot.theory_hours,
            "practice_hours": slot.practice_hours,
            "credits": slot.credits,
            "is_elective": slot.is_elective,
        })
    return {
        "id": plan.id,
        "code": plan.code,
        "name": plan.name,
        "program_code": plan.program.code,
        "total_semesters": plan.total_semesters,
        "semesters": [
            {"semester": number, "subjects": subjects} for number, subjects in sorted(semesters.items())
        ],
    }


def list_plans(db: Session) -> list[dict[str, Any]]:
    counts = dict(
        db.query(CurriculumSubject.plan_id, func.count(CurriculumSubject.id))
        .group_by(CurriculumSubject.plan_id)
        .all()
    )
    return [
        {
            "id": plan.id,
            "code": plan.code,
            "name": plan.name,
            "program_code": plan.program.code,
            "total_semesters": plan.total_semesters,
            "subject_count": counts.get(plan.id, 0),
        }
        for plan in db.query(CurriculumPlan).order_by(CurriculumPlan.id)
    ]
