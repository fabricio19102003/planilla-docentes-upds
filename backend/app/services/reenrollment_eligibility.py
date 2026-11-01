"""What a student takes next term: semester, regular/recursado/pending subjects, scholarship and amounts.

Rules (odd/tasks/student-portal.md S3, S6):
- The primary semester is the curriculum semester with the most distinct subjects in the student's
  last regular term (I or II, any status), ties to the higher one; the target is the next one, capped
  at the last semester of the plan.
- Recursado: a subject with a ``reprobado`` record and no ``aprobado`` one (1200 Bs each, charged for 3
  at most). Pending: an earlier-semester subject that is only ``retirado``, offered without the fee.
  Subjects with a ``pendiente`` record are still in progress and are neither.
- Scholarships need a history without any ``reprobado`` record. The average uses the last regular term
  with final grades (``aprobado``/``reprobado``), so ``retirado`` and ungraded subjects never count.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.academic_records import CurriculumPlan, CurriculumSubject, Student, StudentSubjectRecord
from app.services import academic_records_service
from app.services.academic_records_queries import term_sort_key

REGULAR_KINDS = ("I", "II")
# The legacy exports use these codes for the curriculum subjects on the right.
SUBJECT_EQUIVALENCES = {"SPC 0100": "SCP 0100", "SVB 0800": "CVB 0800"}
ELECTIVE_PREFIX = "ELE "
RECURSADO_FEE = 1200
RECURSADO_CHARGED_MAX = 3
CUOTAS = 5
SCHOLARSHIPS = (  # (category, label, average must exceed, fee per cuota)
    ("fundador", "Beca Fundador", 64, 850),
    ("desafio", "Beca Desafío", 61, 1300),
)
NO_SCHOLARSHIP = ("sin_beca", "Sin beca", None, 1600)


def _plan(db: Session, student: Student) -> CurriculumPlan:
    if student.curriculum_plan_id:
        return db.get(CurriculumPlan, student.curriculum_plan_id)
    return academic_records_service.load_default_curriculum(db)


def _code(record: StudentSubjectRecord) -> str:
    return SUBJECT_EQUIVALENCES.get(record.subject.code, record.subject.code)


def _item(slot: CurriculumSubject) -> dict[str, Any]:
    return {
        "code": slot.subject.code if slot.subject else None, "name": slot.slot_name,
        "semester": slot.semester, "is_elective": slot.is_elective,
    }


def _scholarship(records: list[StudentSubjectRecord], graded: list[StudentSubjectRecord]) -> dict[str, Any]:
    never_failed = all(record.status != "reprobado" for record in records)
    grades = [record.grade for record in graded if record.status in ("aprobado", "reprobado") and record.grade is not None]
    average = round(sum(grades) / len(grades), 2) if grades else None
    category, label, _, cuota = NO_SCHOLARSHIP
    if never_failed and average is not None:
        for option in SCHOLARSHIPS:
            if average > option[2]:
                category, label, _, cuota = option
                break
    return {
        "category": category, "label": label, "average": average, "never_failed": never_failed,
        "cuota": cuota, "cuotas": CUOTAS, "total": cuota * CUOTAS,
    }


def evaluate(db: Session, student: Student) -> dict[str, Any]:
    records = (
        db.query(StudentSubjectRecord)
        .options(joinedload(StudentSubjectRecord.term), joinedload(StudentSubjectRecord.subject))
        .filter(StudentSubjectRecord.student_id == student.id)
        .all()
    )
    plan = _plan(db, student)
    slots = sorted(plan.subjects, key=lambda slot: (slot.semester, slot.position))
    semester_of = {slot.subject.code: slot.semester for slot in slots if slot.subject}

    regular_terms = sorted({r.term for r in records if r.term.kind in REGULAR_KINDS}, key=term_sort_key)
    last_term = regular_terms[-1] if regular_terms else None
    graded_terms = [t for t in regular_terms if any(
        r.term_id == t.id and r.status in ("aprobado", "reprobado") for r in records
    )]
    graded_term = graded_terms[-1] if graded_terms else None

    primary: Optional[int] = None
    if last_term is not None:
        per_semester: dict[int, set[str]] = {}
        for record in records:
            semester = semester_of.get(_code(record))
            if record.term_id == last_term.id and semester is not None:
                per_semester.setdefault(semester, set()).add(_code(record))
        if per_semester:
            primary = max(per_semester, key=lambda s: (len(per_semester[s]), s))
    target = min(primary + 1, plan.total_semesters) if primary is not None else None

    statuses: dict[str, set[str]] = {}
    for record in records:
        statuses.setdefault(_code(record), set()).add(record.status)
    approved = {code for code, seen in statuses.items() if "aprobado" in seen}
    in_progress = {code for code, seen in statuses.items() if "pendiente" in seen}
    failed = {code for code, seen in statuses.items() if "reprobado" in seen} - approved - in_progress
    approved_electives = sum(1 for code in approved if code.startswith(ELECTIVE_PREFIX))

    regular, recursado, pending = [], [], []
    elective_slots_seen = 0
    for slot in slots:
        code = slot.subject.code if slot.subject else None
        if slot.is_elective and code is None:
            elective_slots_seen += 1
            if target is not None and slot.semester == target and elective_slots_seen > approved_electives:
                regular.append(_item(slot))
            continue
        if code in failed:
            recursado.append(_item(slot))
        elif code in approved or code in in_progress or target is None:
            continue
        elif slot.semester == target:
            regular.append(_item(slot))
        elif slot.semester < target and statuses.get(code) == {"retirado"}:
            pending.append(_item(slot))

    graded = [r for r in records if graded_term is not None and r.term_id == graded_term.id]
    charged = min(len(recursado), RECURSADO_CHARGED_MAX)
    return {
        "last_term": last_term.code if last_term else None,
        "graded_term": graded_term.code if graded_term else None,
        "primary_semester": primary,
        "target_semester": target,
        "regular": regular,
        "recursado": recursado,
        "pending": pending,
        "scholarship": _scholarship(records, graded),
        "recursado_fee": {
            "per_subject": RECURSADO_FEE, "subjects": len(recursado), "charged_subjects": charged,
            "total": charged * RECURSADO_FEE,
        },
    }
