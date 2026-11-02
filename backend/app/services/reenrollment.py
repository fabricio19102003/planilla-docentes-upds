"""Re-enrollment windows, student requests with group capacity, and the staff inbox (student-portal S2, S4-S9)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.academic_management import AcademicGroup
from app.models.academic_records import Student
from app.models.student_portal import (
    ReenrollmentRequest,
    ReenrollmentRequestItem,
    ReenrollmentWindow,
    StudentAccount,
)
from app.models.user import User
from app.services import reenrollment_eligibility as eligibility

BOLIVIA = timezone(timedelta(hours=-4))  # no daylight saving
# Pending and done requests hold their places; an observed one gives them back until it is resubmitted.
HOLDING_STATUSES = ("pendiente", "realizada")
OBSERVATION_LABELS = {
    "documentos_migracion": "Documentos de migración", "pago_pendiente": "Pago pendiente", "otro": "Otro",
}


def bolivia_today() -> date:
    return datetime.now(BOLIVIA).date()


# ── Windows ──────────────────────────────────────────────────────────────────

def window_payload(window: Optional[ReenrollmentWindow]) -> Optional[dict[str, Any]]:
    if window is None:
        return None
    today = bolivia_today()
    return {
        "id": window.id, "term_code": window.term_code, "starts_on": window.starts_on,
        "ends_on": window.ends_on, "is_open": window.starts_on <= today <= window.ends_on,
    }


def list_windows(db: Session) -> list[dict[str, Any]]:
    windows = db.query(ReenrollmentWindow).order_by(ReenrollmentWindow.starts_on.desc()).all()
    counts: dict[tuple[int, str], int] = {
        (window_id, status): count
        for window_id, status, count in db.query(
            ReenrollmentRequest.window_id, ReenrollmentRequest.status, func.count()
        ).group_by(ReenrollmentRequest.window_id, ReenrollmentRequest.status)
    }
    return [
        {**window_payload(w), "requests": {s: counts.get((w.id, s), 0) for s in ("pendiente", "realizada", "observada")}}
        for w in windows
    ]


def create_window(db: Session, term_code: str, starts_on: date, ends_on: date, actor: User) -> ReenrollmentWindow:
    if db.query(ReenrollmentWindow).filter(ReenrollmentWindow.term_code == term_code).first():
        raise HTTPException(status_code=409, detail=f"Ya existe una ventana de rematrícula para {term_code}")
    window = ReenrollmentWindow(term_code=term_code, starts_on=starts_on, ends_on=ends_on, created_by=actor.id)
    db.add(window)
    db.flush()
    return window


def get_window(db: Session, window_id: int) -> ReenrollmentWindow:
    window = db.get(ReenrollmentWindow, window_id)
    if window is None:
        raise HTTPException(status_code=404, detail="Ventana de rematrícula no encontrada")
    return window


def current_window(db: Session) -> Optional[ReenrollmentWindow]:
    """The open window, else the next one to open, else the last one that closed."""
    today = bolivia_today()
    query = db.query(ReenrollmentWindow)
    return (
        query.filter(ReenrollmentWindow.starts_on <= today, ReenrollmentWindow.ends_on >= today)
        .order_by(ReenrollmentWindow.starts_on.desc()).first()
        or query.filter(ReenrollmentWindow.starts_on > today).order_by(ReenrollmentWindow.starts_on).first()
        or query.order_by(ReenrollmentWindow.ends_on.desc()).first()
    )


# ── Groups and places ────────────────────────────────────────────────────────

def _taken(db: Session, group_ids: list[int], exclude_request_id: Optional[int] = None) -> dict[int, int]:
    if not group_ids:
        return {}
    holding = db.query(ReenrollmentRequest.id).filter(ReenrollmentRequest.status.in_(HOLDING_STATUSES))
    if exclude_request_id is not None:
        holding = holding.filter(ReenrollmentRequest.id != exclude_request_id)
    holding_ids = holding.subquery()
    # A place is a student: retaking a subject in one's own main group does not take a second one.
    members: dict[int, set[int]] = {}
    for group_id, request_id in (
        db.query(ReenrollmentRequest.main_group_id, ReenrollmentRequest.id)
        .filter(ReenrollmentRequest.id.in_(holding_ids.select()), ReenrollmentRequest.main_group_id.in_(group_ids))
    ):
        members.setdefault(group_id, set()).add(request_id)
    for group_id, request_id in (
        db.query(ReenrollmentRequestItem.group_id, ReenrollmentRequestItem.request_id)
        .filter(ReenrollmentRequestItem.request_id.in_(holding_ids.select()),
                ReenrollmentRequestItem.group_id.in_(group_ids))
    ):
        members.setdefault(group_id, set()).add(request_id)
    return {group_id: len(ids) for group_id, ids in members.items()}


def _group_payload(group: AcademicGroup, taken: int) -> dict[str, Any]:
    free = None if group.expected_size is None else max(group.expected_size - taken, 0)
    return {
        "id": group.id, "code": group.code, "shift": group.shift, "semester": group.semester,
        "capacity": group.expected_size, "taken": taken, "free": free, "is_full": free == 0,
    }


def groups_for(db: Session, window: ReenrollmentWindow, semesters: set[int],
               exclude_request_id: Optional[int] = None) -> dict[int, list[dict[str, Any]]]:
    groups = (
        db.query(AcademicGroup)
        .filter(AcademicGroup.academic_period == window.term_code, AcademicGroup.semester.in_(semesters),
                AcademicGroup.active.is_(True))
        .order_by(AcademicGroup.semester, AcademicGroup.code)
        .all()
    ) if semesters else []
    taken = _taken(db, [g.id for g in groups], exclude_request_id)
    by_semester: dict[int, list[dict[str, Any]]] = {s: [] for s in semesters}
    for group in groups:
        by_semester[group.semester].append(_group_payload(group, taken.get(group.id, 0)))
    return by_semester


# ── Requests ─────────────────────────────────────────────────────────────────

def serialize_request(request: Optional[ReenrollmentRequest]) -> Optional[dict[str, Any]]:
    if request is None:
        return None
    return {
        "id": request.id, "window_id": request.window_id, "term_code": request.window.term_code,
        "target_semester": request.target_semester, "status": request.status,
        "main_group": {"id": request.main_group.id, "code": request.main_group.code, "shift": request.main_group.shift},
        "items": [
            {"kind": item.kind, "subject_code": item.subject_code, "subject_name": item.subject_name,
             "semester": item.semester, "group": {"id": item.group.id, "code": item.group.code,
                                                   "shift": item.group.shift}}
            for item in request.items
        ],
        "observation_reason": request.observation_reason,
        "observation_label": OBSERVATION_LABELS.get(request.observation_reason or ""),
        "observation_message": request.observation_message,
        "snapshot": request.snapshot, "submitted_at": request.submitted_at, "handled_at": request.handled_at,
    }


def _request_for(db: Session, student_id: int, window: ReenrollmentWindow) -> Optional[ReenrollmentRequest]:
    return (
        db.query(ReenrollmentRequest)
        .filter(ReenrollmentRequest.student_id == student_id, ReenrollmentRequest.window_id == window.id)
        .one_or_none()
    )


def student_view(db: Session, account: StudentAccount) -> dict[str, Any]:
    window = current_window(db)
    result = eligibility.evaluate(db, account.student)
    request = _request_for(db, account.student_id, window) if window else None
    main_groups: list[dict[str, Any]] = []
    other_groups: dict[int, list[dict[str, Any]]] = {}
    if window and result["target_semester"] is not None:
        extra = {item["semester"] for item in result["recursado"] + result["pending"]}
        groups = groups_for(db, window, {result["target_semester"], *extra}, request.id if request else None)
        main_groups = groups[result["target_semester"]]
        other_groups = {semester: groups[semester] for semester in extra}
    return {
        "window": window_payload(window), "eligibility": result, "main_groups": main_groups,
        "groups_by_semester": other_groups, "request": serialize_request(request),
    }


def _lock_groups(db: Session, group_ids: set[int]) -> dict[int, AcademicGroup]:
    # Row locks in id order serialize concurrent requests for the same places (no-op on SQLite,
    # which serializes writers anyway).
    rows = (
        db.query(AcademicGroup).filter(AcademicGroup.id.in_(sorted(group_ids)))
        .order_by(AcademicGroup.id).with_for_update().all()
    )
    return {group.id: group for group in rows}


def _ensure_places(db: Session, groups: dict[int, AcademicGroup], group_ids: set[int],
                   exclude_request_id: Optional[int]) -> None:
    """Refuse when one more student does not fit; the caller holds the row locks of ``groups``."""
    taken = _taken(db, list(group_ids), exclude_request_id)
    for group_id in sorted(group_ids):
        group = groups[group_id]
        if group.expected_size is not None and taken.get(group_id, 0) + 1 > group.expected_size:
            raise HTTPException(status_code=409, detail=f"El grupo {group.code} ya no tiene cupos")


def submit(db: Session, account: StudentAccount, main_group_id: int, items: list[dict[str, Any]]) -> ReenrollmentRequest:
    window = current_window(db)
    if window is None or not window_payload(window)["is_open"]:
        raise HTTPException(status_code=409, detail="La rematrícula no está abierta")
    existing = _request_for(db, account.student_id, window)
    if existing is not None and existing.status == "realizada":
        raise HTTPException(status_code=409, detail="Tu rematrícula ya fue realizada")
    result = eligibility.evaluate(db, account.student)
    if result["target_semester"] is None:
        raise HTTPException(status_code=422, detail="No encontramos tu historial; acercate a Registro")
    offered = {s["code"]: ("recursado", s) for s in result["recursado"]}
    offered.update({s["code"]: ("pendiente", s) for s in result["pending"]})

    chosen: dict[str, int] = {}
    for item in items:
        if item["subject_code"] not in offered:
            raise HTTPException(status_code=422, detail=f"{item['subject_code']} no está entre tus materias a recursar")
        chosen[item["subject_code"]] = item["group_id"]
    groups = _lock_groups(db, {main_group_id, *chosen.values()})

    def check(group_id: int, semester: int, message: str) -> AcademicGroup:
        group = groups.get(group_id)
        if group is None or not group.active or group.academic_period != window.term_code or group.semester != semester:
            raise HTTPException(status_code=422, detail=message)
        return group

    main = check(main_group_id, result["target_semester"], "El grupo elegido no corresponde a tu semestre")
    for code, group_id in chosen.items():
        check(group_id, offered[code][1]["semester"], f"El grupo de {code} debe ser del semestre {offered[code][1]['semester']}")
    _ensure_places(db, groups, {main_group_id, *chosen.values()}, existing.id if existing else None)

    request = existing or ReenrollmentRequest(student_id=account.student_id, window_id=window.id)
    request.target_semester = result["target_semester"]
    request.main_group_id = main.id
    request.status = "pendiente"
    request.observation_reason = None
    request.observation_message = None
    chosen_recursado = sum(1 for code in chosen if offered[code][0] == "recursado")
    charged = min(chosen_recursado, eligibility.RECURSADO_CHARGED_MAX)
    request.snapshot = {
        **{k: result[k] for k in ("scholarship", "regular", "recursado", "pending",
                                  "primary_semester", "last_term", "graded_term")},
        # The fee follows what the student chose to retake, not every subject offered.
        "recursado_fee": {"per_subject": eligibility.RECURSADO_FEE, "subjects": chosen_recursado,
                          "charged_subjects": charged, "total": charged * eligibility.RECURSADO_FEE},
    }
    request.submitted_at = datetime.utcnow()
    request.handled_by = None
    request.handled_at = None
    # Update items in place: replacing the list would insert before deleting and hit the unique subject key.
    current = {item.subject_code: item for item in request.items}
    request.items = [item for code, item in current.items() if code in chosen]
    for code, group_id in chosen.items():
        item = current.get(code)
        if item is None:
            item = ReenrollmentRequestItem(subject_code=code)
            request.items.append(item)
        item.kind, item.subject_name = offered[code][0], offered[code][1]["name"]
        item.semester, item.group_id = offered[code][1]["semester"], group_id
    if existing is None:
        db.add(request)
    try:
        db.flush()
    except IntegrityError as exc:  # the same student submitting twice at once
        db.rollback()
        raise HTTPException(status_code=409, detail="Tu solicitud ya se está registrando; recargá la página") from exc
    db.refresh(request)
    return request


# ── Staff inbox ──────────────────────────────────────────────────────────────

def inbox(db: Session, *, window_id: Optional[int], status: Optional[str], semester: Optional[int],
          group_id: Optional[int], foreign: Optional[bool], search: Optional[str], page: int, page_size: int):
    window = get_window(db, window_id) if window_id else current_window(db)
    if window is None:
        return {"window": None, "items": [], "total": 0, "page": page, "page_size": page_size}
    query = (
        db.query(ReenrollmentRequest).join(Student, Student.id == ReenrollmentRequest.student_id)
        .options(joinedload(ReenrollmentRequest.main_group), joinedload(ReenrollmentRequest.items))
        .filter(ReenrollmentRequest.window_id == window.id)
    )
    if status:
        query = query.filter(ReenrollmentRequest.status == status)
    if semester:
        query = query.filter(ReenrollmentRequest.target_semester == semester)
    if group_id:
        in_items = db.query(ReenrollmentRequestItem.request_id).filter(ReenrollmentRequestItem.group_id == group_id)
        query = query.filter(or_(ReenrollmentRequest.main_group_id == group_id, ReenrollmentRequest.id.in_(in_items)))
    if foreign is not None:
        query = query.filter(Student.is_foreign.is_(foreign))
    if search:
        like = f"%{search.strip()}%"
        query = query.filter(or_(Student.document_number.ilike(like), Student.first_names.ilike(like),
                                 Student.last_names.ilike(like)))
    total = query.count()
    rows = (
        query.order_by(ReenrollmentRequest.submitted_at, ReenrollmentRequest.id)
        .offset((page - 1) * page_size).limit(page_size).all()
    )
    items = [
        {
            "id": r.id, "student_id": r.student_id, "document_number": r.student.document_number,
            "full_name": r.student.full_name, "is_foreign": r.student.is_foreign,
            "target_semester": r.target_semester, "main_group_code": r.main_group.code,
            "main_group_shift": r.main_group.shift, "status": r.status,
            "recursado_count": sum(1 for i in r.items if i.kind == "recursado"),
            "pending_count": sum(1 for i in r.items if i.kind == "pendiente"),
            "scholarship_label": (r.snapshot.get("scholarship") or {}).get("label"),
            "submitted_at": r.submitted_at,
        }
        for r in rows
    ]
    return {"window": window_payload(window), "items": items, "total": total, "page": page, "page_size": page_size}


def get_request(db: Session, request_id: int) -> ReenrollmentRequest:
    request = db.get(ReenrollmentRequest, request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Solicitud de rematrícula no encontrada")
    return request


def handle(db: Session, request: ReenrollmentRequest, actor: User, status: str,
           reason: Optional[str] = None, message: Optional[str] = None) -> ReenrollmentRequest:
    if status != "pendiente" and request.status == status:
        raise HTTPException(status_code=409, detail="La solicitud ya está en ese estado")
    if status in HOLDING_STATUSES and request.status not in HOLDING_STATUSES:
        # An observed request gave its places back; taking them again must fit like a new request.
        group_ids = {request.main_group_id, *(item.group_id for item in request.items)}
        _ensure_places(db, _lock_groups(db, group_ids), group_ids, request.id)
    request.status = status
    request.observation_reason = reason
    request.observation_message = message
    request.handled_by = actor.id
    request.handled_at = datetime.utcnow()
    db.flush()
    return request
