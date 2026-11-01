"""Read models for academic terms, students and their history."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.academic_records import AcademicTerm, CurriculumPlan, Student, StudentSubjectRecord

# Chronological order of the terms within one year.
TERM_ORDER = {"VER": 0, "I": 1, "INV": 2, "II": 3}


def term_sort_key(term: AcademicTerm) -> tuple[int, int]:
    return term.year, TERM_ORDER[term.kind]


def _term(term: AcademicTerm) -> dict[str, Any]:
    return {"code": term.code, "name": term.name, "year": term.year, "kind": term.kind,
            "is_intensive": term.is_intensive}


def list_terms(db: Session) -> list[dict[str, Any]]:
    counts = dict(
        db.query(StudentSubjectRecord.term_id, func.count(StudentSubjectRecord.id))
        .group_by(StudentSubjectRecord.term_id)
        .all()
    )
    terms = sorted(db.query(AcademicTerm), key=term_sort_key, reverse=True)
    return [{**_term(term), "id": term.id, "record_count": counts.get(term.id, 0)} for term in terms]


def list_students(
    db: Session, *, search: Optional[str], status: Optional[str], foreign: Optional[bool],
    page: int, page_size: int,
) -> dict[str, Any]:
    query = db.query(Student)
    if search and search.strip():
        pattern = f"%{search.strip().lower()}%"
        query = query.filter(or_(
            func.lower(Student.document_number).like(pattern),
            func.lower(Student.first_names + " " + Student.last_names).like(pattern),
        ))
    if status:
        query = query.filter(Student.legacy_enrollment_status == status)
    if foreign is not None:
        query = query.filter(Student.is_foreign.is_(foreign))
    total = query.count()
    students = (
        query.order_by(Student.last_names, Student.first_names, Student.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    terms_by_student: dict[int, list[AcademicTerm]] = {}
    record_counts: dict[int, int] = {}
    if students:
        ids = [s.id for s in students]
        rows = (
            db.query(StudentSubjectRecord.student_id, StudentSubjectRecord.term_id, func.count(StudentSubjectRecord.id))
            .filter(StudentSubjectRecord.student_id.in_(ids))
            .group_by(StudentSubjectRecord.student_id, StudentSubjectRecord.term_id)
            .all()
        )
        term_map = {t.id: t for t in db.query(AcademicTerm).filter(AcademicTerm.id.in_({r[1] for r in rows}))}
        for student_id, term_id, count in rows:
            terms_by_student.setdefault(student_id, []).append(term_map[term_id])
            record_counts[student_id] = record_counts.get(student_id, 0) + count
    items = []
    for student in students:
        terms = terms_by_student.get(student.id, [])
        items.append({
            "id": student.id,
            "document_number": student.document_number,
            "full_name": student.full_name,
            "nationality": student.nationality,
            "is_foreign": student.is_foreign,
            "legacy_enrollment_status": student.legacy_enrollment_status,
            "last_term": max(terms, key=term_sort_key).code if terms else None,
            "record_count": record_counts.get(student.id, 0),
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def student_detail(db: Session, student: Student) -> dict[str, Any]:
    plan = db.get(CurriculumPlan, student.curriculum_plan_id) if student.curriculum_plan_id else None
    curriculum = {slot.subject.code for slot in plan.subjects if slot.subject} if plan else set()
    records = (
        db.query(StudentSubjectRecord)
        .options(joinedload(StudentSubjectRecord.term), joinedload(StudentSubjectRecord.subject))
        .filter(StudentSubjectRecord.student_id == student.id)
        .all()
    )
    by_term: dict[int, list[StudentSubjectRecord]] = {}
    for record in records:
        by_term.setdefault(record.term_id, []).append(record)
    history = []
    for term_records in sorted(by_term.values(), key=lambda items: term_sort_key(items[0].term), reverse=True):
        history.append({
            "term": _term(term_records[0].term),
            "records": [
                {
                    "legacy_registration_id": record.legacy_registration_id,
                    "subject_code": record.subject.code,
                    "subject_name": record.subject.name,
                    "group_code": record.group_code,
                    "shift": record.shift,
                    "teacher_name": record.teacher_name,
                    "status": record.status,
                    "grade": record.grade,
                    "in_curriculum": record.subject.code in curriculum,
                }
                for record in sorted(term_records, key=lambda item: (item.subject.name, item.legacy_registration_id))
            ],
        })
    return {
        "student": {
            "id": student.id,
            "document_number": student.document_number,
            "document_type": student.document_type,
            "first_names": student.first_names,
            "last_names": student.last_names,
            "full_name": student.full_name,
            "birth_date": student.birth_date.isoformat() if student.birth_date else None,
            "gender": student.gender,
            "phone": student.phone,
            "personal_email": student.personal_email,
            "academic_email": student.academic_email,
            "birth_country": student.birth_country,
            "nationality": student.nationality,
            "is_foreign": student.is_foreign,
            "school": student.school,
            "address": student.address,
            "legacy_enrollment_status": student.legacy_enrollment_status,
            "curriculum_plan": plan.name if plan else None,
        },
        "history": history,
    }
