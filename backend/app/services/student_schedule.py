"""The published schedule a student sees: main group, recursado/pending groups and intensive courses (academic-phase3 S3)."""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from app.models.academic_management import AcademicGroup, AcademicSchedulePublication, AcademicSchedulePublishedBlock
from app.models.intensive_courses import IntensiveCourse, IntensiveEnrollment
from app.models.student_portal import ReenrollmentRequest, ReenrollmentWindow, StudentAccount
from app.services import reenrollment
from app.services.academic_schedule_publication_service import _effective_publication, _publication_query

NO_REQUEST = "Todavía no enviaste tu solicitud de rematrícula."
NOT_DONE = "Tu horario aparece cuando Registro complete tu rematrícula."
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
SOURCE_ORDER = {"grupo": 0, "recursado": 1, "pendiente": 2, "intensivo": 3}


def _not_published(term_code: str) -> str:
    return f"El horario de {term_code} todavía no fue publicado."


def _status(code: str, message: Optional[str]) -> dict[str, Any]:
    return {"code": code, "message": message}


def _publication_for(db: Session, program_id: int, term_code: str, today: date) -> Optional[AcademicSchedulePublication]:
    """The publication in force today; else the next one to take effect, so the coming term can be seen early."""
    current = _effective_publication(db, program_id, term_code, today)
    if current is not None:
        return current
    return _publication_query(db).filter(
        AcademicSchedulePublication.program_id == program_id,
        AcademicSchedulePublication.academic_period == term_code,
        AcademicSchedulePublication.effective_from > today,
    ).order_by(
        AcademicSchedulePublication.effective_from,
        AcademicSchedulePublication.sequence.desc(),
        AcademicSchedulePublication.id.desc(),
    ).first()


def _publications_for_term(db: Session, term_code: str, today: date) -> list[AcademicSchedulePublication]:
    program_ids = [row[0] for row in db.query(distinct(AcademicSchedulePublication.program_id)).filter(
        AcademicSchedulePublication.academic_period == term_code).order_by(AcademicSchedulePublication.program_id)]
    found = (_publication_for(db, program_id, term_code, today) for program_id in program_ids)
    return [publication for publication in found if publication is not None]


def _teacher(block: AcademicSchedulePublishedBlock, on: date):
    return next((
        item for item in sorted(block.assignments, key=lambda a: (a.effective_from, a.id))
        if item.effective_from <= on and (item.effective_to is None or item.effective_to >= on)
    ), None)


def _entry(source: str, block: AcademicSchedulePublishedBlock, publication: AcademicSchedulePublication,
           term_code: str, today: date) -> dict[str, Any]:
    upcoming = publication.effective_from > today
    assignment = _teacher(block, publication.effective_from if upcoming else today)
    return {
        "source": source, "subject_code": block.subject_code, "subject_name": block.subject_name,
        "group_code": block.group_code, "weekday": block.weekday,
        "start_time": block.start_time.strftime("%H:%M"), "end_time": block.end_time.strftime("%H:%M"),
        "classroom": {"code": block.classroom_code, "name": block.classroom_name},
        "activity_type": block.activity_type,
        "teacher_name": assignment.teacher_name if assignment else None, "term_code": term_code,
        "effective_from": publication.effective_from.isoformat(), "is_upcoming": upcoming,
    }


def _request_entries(db: Session, request: ReenrollmentRequest, today: date) -> tuple[list[dict[str, Any]], Optional[dict], str]:
    term_code = request.window.term_code
    publications: dict[int, Optional[AcademicSchedulePublication]] = {}

    def publication_of(group_id: int) -> Optional[AcademicSchedulePublication]:
        program_id = db.get(AcademicGroup, group_id).program_id
        if program_id not in publications:
            publications[program_id] = _publication_for(db, program_id, term_code, today)
        return publications[program_id]

    main = publication_of(request.main_group_id)
    if main is None:
        return [], None, term_code
    regular = {item["code"] for item in (request.snapshot or {}).get("regular", []) if item.get("code")}
    wanted = [("grupo", request.main_group_id, lambda code: code in regular)]
    wanted += [(item.kind, item.group_id, lambda code, item=item: code == item.subject_code)
               for item in request.items]
    entries: list[dict[str, Any]] = []
    seen: set[int] = set()
    for source, group_id, subject_matches in wanted:
        publication = publication_of(group_id)
        if publication is None:
            continue
        for block in publication.blocks:
            if block.source_group_id == group_id and subject_matches(block.subject_code) and block.id not in seen:
                seen.add(block.id)
                entries.append(_entry(source, block, publication, term_code, today))
    return entries, {"term_code": term_code, "effective_from": main.effective_from.isoformat()}, term_code


def _course_blocks(course: IntensiveCourse, publications: list[AcademicSchedulePublication], today: date):
    matching = [(block, publication) for publication in publications for block in publication.blocks
                if block.subject_code == course.subject.code]
    if len({block.source_group_id for block, _ in matching}) <= 1:
        return matching
    # Several groups teach the subject: the course is the one its teacher gives.
    return [
        (block, publication) for block, publication in matching
        if (assignment := _teacher(block, publication.effective_from if publication.effective_from > today else today))
        and assignment.teacher_ci == course.teacher_ci
    ]


def _intensive_entries(db: Session, account: StudentAccount, today: date):
    courses = (
        db.query(IntensiveCourse).join(IntensiveEnrollment, IntensiveEnrollment.course_id == IntensiveCourse.id)
        .filter(IntensiveEnrollment.student_id == account.student_id)
        .order_by(IntensiveCourse.term_code, IntensiveCourse.id).all()
    )
    publications: dict[str, list[AcademicSchedulePublication]] = {}
    entries: list[dict[str, Any]] = []
    unscheduled: list[dict[str, Any]] = []
    for course in courses:
        if course.term_code not in publications:
            publications[course.term_code] = _publications_for_term(db, course.term_code, today)
        blocks = _course_blocks(course, publications[course.term_code], today)
        if not blocks:
            unscheduled.append({
                "source": "intensivo", "subject_code": course.subject.code, "subject_name": course.subject.name,
                "term_code": course.term_code,
            })
        entries.extend(_entry("intensivo", block, publication, course.term_code, today)
                       for block, publication in blocks)
    return entries, unscheduled


def student_schedule(db: Session, account: StudentAccount) -> dict[str, Any]:
    today = reenrollment.bolivia_today()
    entries: list[dict[str, Any]] = []
    publication: Optional[dict] = None
    # A new window (even scheduled in advance) must not hide the term in progress: among the done
    # requests, the one whose schedule is in force today wins; else the newest one (its next publication).
    done = (
        db.query(ReenrollmentRequest).join(ReenrollmentWindow, ReenrollmentWindow.id == ReenrollmentRequest.window_id)
        .filter(ReenrollmentRequest.student_id == account.student_id, ReenrollmentRequest.status == "realizada")
        .order_by(ReenrollmentWindow.starts_on.desc(), ReenrollmentRequest.id.desc()).all()
    )
    built = [_request_entries(db, request, today) for request in done]
    chosen = next((b for b in built if b[1] and date.fromisoformat(b[1]["effective_from"]) <= today), None) \
        or next((b for b in built if b[1]), None) or (built[0] if built else None)
    if chosen is not None:
        entries, publication, term_code = chosen
        status = _status("ok", None) if publication else _status("not_published", _not_published(term_code))
    else:
        window = reenrollment.current_window(db)
        request = reenrollment._request_for(db, account.student_id, window) if window else None
        status = _status("no_request", NO_REQUEST) if request is None else _status("not_done", NOT_DONE)
    intensive, unscheduled = _intensive_entries(db, account, today)
    entries += intensive
    entries.sort(key=lambda e: (WEEKDAYS.index(e["weekday"]) if e["weekday"] in WEEKDAYS else len(WEEKDAYS),
                                e["start_time"], SOURCE_ORDER[e["source"]], e["subject_code"]))
    return {
        "status": status, "effective_from": publication["effective_from"] if publication else None,
        "entries": entries, "unscheduled": unscheduled,
    }
