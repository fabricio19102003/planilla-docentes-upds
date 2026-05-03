"""DesignationService — manages designations through the scheduling module (E6).

Creates designations with both FK columns AND legacy string columns populated
in parallel. Integrates with SlotService for scheduling and CompatibilityAdapter
for schedule_json sync.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.designation import Designation
from app.models.teacher import Teacher
from app.scheduling.models.academic_period import AcademicPeriod
from app.scheduling.models.designation_slot import DesignationSlot
from app.scheduling.models.group import Group
from app.scheduling.models.semester import Semester
from app.scheduling.models.subject import Subject
from app.scheduling.services.compatibility_adapter import CompatibilityAdapter
from app.scheduling.services.conflict_service import ConflictService
from app.scheduling.services.slot_service import SlotService

logger = logging.getLogger(__name__)

_compat = CompatibilityAdapter()
_conflict_svc = ConflictService()
_slot_svc = SlotService()


class DesignationService:
    """Manages designations through the scheduling module with full lifecycle."""

    # ─── Create ───────────────────────────────────────────────────────

    def create_designation(
        self,
        db: Session,
        *,
        teacher_ci: str,
        period_id: int,
        subject_id: int,
        group_id: int,
        slots: list[dict] | None = None,
        semester_hours: int | None = None,
    ) -> dict[str, Any]:
        """Create a new designation with status='draft', source='manual'.

        Steps:
        1. Validate teacher, period, subject, group all exist
        2. Validate group belongs to the correct period
        3. Create Designation with both FK columns AND string columns populated
        4. If slots provided, create DesignationSlots via SlotService
        5. Sync schedule_json via CompatibilityAdapter
        6. Return designation with slots
        """
        # 1. Validate entities exist
        teacher = db.query(Teacher).filter(Teacher.ci == teacher_ci).first()
        if not teacher:
            raise HTTPException(status_code=404, detail=f"Docente con CI '{teacher_ci}' no encontrado")

        period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
        if not period:
            raise HTTPException(status_code=404, detail=f"Periodo académico con id {period_id} no encontrado")

        subject = db.query(Subject).filter(Subject.id == subject_id).first()
        if not subject:
            raise HTTPException(status_code=404, detail=f"Materia con id {subject_id} no encontrada")

        group = db.query(Group).filter(Group.id == group_id).first()
        if not group:
            raise HTTPException(status_code=404, detail=f"Grupo con id {group_id} no encontrado")

        # 2. Validate group belongs to the period
        if group.academic_period_id != period_id:
            raise HTTPException(
                status_code=422,
                detail=f"Grupo '{group.code}' no pertenece al periodo '{period.code}' "
                       f"(pertenece al periodo_id={group.academic_period_id})",
            )

        # Derive semester name from group -> semester
        semester_obj = db.query(Semester).filter(Semester.id == group.semester_id).first()
        semester_name = semester_obj.name if semester_obj else "N/A"

        # Detect designation_type from subject name (heuristic)
        designation_type = "regular"
        subject_lower = subject.name.lower()
        if any(kw in subject_lower for kw in ("práctica", "practica", "asistencial", "laboratorio")):
            designation_type = "practice"

        # 3. Create Designation with BOTH FK and string columns
        designation = Designation(
            teacher_ci=teacher_ci,
            academic_period_id=period_id,
            academic_period=period.code,
            subject_id=subject_id,
            subject=subject.name,
            group_id=group_id,
            group_code=group.code,
            semester=semester_name,
            source="manual",
            status="draft",
            schedule_json=[],
            designation_type=designation_type,
            semester_hours=semester_hours,
        )
        db.add(designation)
        db.flush()  # Get designation.id

        # 4. Create slots if provided
        created_slots = []
        slot_errors = []
        if slots:
            for slot_data in slots:
                try:
                    result = _slot_svc.create_slot(
                        db,
                        designation_id=designation.id,
                        day_of_week=slot_data["day_of_week"],
                        start_time=slot_data["start_time"],
                        end_time=slot_data["end_time"],
                        room_id=slot_data.get("room_id"),
                    )
                    if result["blocked"]:
                        slot_errors.append({
                            "slot": slot_data,
                            "conflicts": result["conflicts"],
                        })
                    elif result["slot"]:
                        created_slots.append(result["slot"])
                except HTTPException as exc:
                    slot_errors.append({
                        "slot": slot_data,
                        "error": exc.detail,
                    })

        # 5. Sync schedule_json (also done inside create_slot, but ensure final state)
        _compat.sync_designation_json(db, designation.id)

        logger.info(
            "Created designation %d for teacher %s, subject=%s, group=%s, period=%s",
            designation.id, teacher_ci, subject.name, group.code, period.code,
        )

        return self._to_response(db, designation, created_slots, slot_errors)

    # ─── Confirm ──────────────────────────────────────────────────────

    def confirm_designation(self, db: Session, designation_id: int) -> dict[str, Any]:
        """Status: draft -> confirmed. Validates no unresolved HARD conflicts."""
        designation = self._get_or_404(db, designation_id)

        if designation.status == "confirmed":
            raise HTTPException(status_code=422, detail="La designación ya está confirmada")
        if designation.status == "cancelled":
            raise HTTPException(status_code=422, detail="No se puede confirmar una designación cancelada")

        # Check for HARD conflicts on all slots
        slots = (
            db.query(DesignationSlot)
            .filter(DesignationSlot.designation_id == designation_id)
            .all()
        )
        hard_conflicts = []
        for slot in slots:
            period_id, group_id = _slot_svc._resolve_context(db, designation)
            if period_id:
                conflicts = _conflict_svc.validate_slot(
                    db,
                    period_id=period_id,
                    designation_id=designation_id,
                    teacher_ci=designation.teacher_ci,
                    group_id=group_id or 0,
                    day_of_week=slot.day_of_week,
                    start_time=slot.start_time,
                    end_time=slot.end_time,
                    room_id=slot.room_id,
                    exclude_slot_id=slot.id,
                )
                hard_conflicts.extend(c for c in conflicts if c.severity == "HARD")

        if hard_conflicts:
            raise HTTPException(
                status_code=422,
                detail=f"No se puede confirmar: {len(hard_conflicts)} conflicto(s) HARD sin resolver",
            )

        designation.status = "confirmed"
        db.flush()
        logger.info("Confirmed designation %d", designation_id)
        return self._to_response(db, designation)

    # ─── Cancel ───────────────────────────────────────────────────────

    def cancel_designation(self, db: Session, designation_id: int) -> dict[str, Any]:
        """Status: draft|confirmed -> cancelled."""
        designation = self._get_or_404(db, designation_id)

        if designation.status == "cancelled":
            raise HTTPException(status_code=422, detail="La designación ya está cancelada")

        designation.status = "cancelled"
        db.flush()
        logger.info("Cancelled designation %d", designation_id)
        return self._to_response(db, designation)

    # ─── Update ───────────────────────────────────────────────────────

    def update_designation(self, db: Session, designation_id: int, **fields: Any) -> dict[str, Any]:
        """Update non-slot fields. Validates status allows editing (not cancelled)."""
        designation = self._get_or_404(db, designation_id)

        if designation.status == "cancelled":
            raise HTTPException(status_code=422, detail="No se puede editar una designación cancelada")

        if "subject_id" in fields and fields["subject_id"] is not None:
            subject = db.query(Subject).filter(Subject.id == fields["subject_id"]).first()
            if not subject:
                raise HTTPException(status_code=404, detail=f"Materia con id {fields['subject_id']} no encontrada")
            designation.subject_id = subject.id
            designation.subject = subject.name

        if "group_id" in fields and fields["group_id"] is not None:
            group = db.query(Group).filter(Group.id == fields["group_id"]).first()
            if not group:
                raise HTTPException(status_code=404, detail=f"Grupo con id {fields['group_id']} no encontrado")
            # Validate group belongs to the same period
            if designation.academic_period_id and group.academic_period_id != designation.academic_period_id:
                raise HTTPException(
                    status_code=422,
                    detail=f"Grupo '{group.code}' no pertenece al periodo de esta designación",
                )
            designation.group_id = group.id
            designation.group_code = group.code
            # Update semester from group
            semester_obj = db.query(Semester).filter(Semester.id == group.semester_id).first()
            if semester_obj:
                designation.semester = semester_obj.name

        if "semester_hours" in fields:
            designation.semester_hours = fields["semester_hours"]

        db.flush()
        logger.info("Updated designation %d", designation_id)
        return self._to_response(db, designation)

    # ─── List ─────────────────────────────────────────────────────────

    def list_designations(
        self,
        db: Session,
        *,
        period_id: int | None = None,
        teacher_ci: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List designations with filters."""
        query = db.query(Designation)

        if period_id is not None:
            # Search by FK first, fall back to string match
            period = db.query(AcademicPeriod).filter(AcademicPeriod.id == period_id).first()
            if period:
                query = query.filter(
                    (Designation.academic_period_id == period_id)
                    | (Designation.academic_period == period.code)
                )
            else:
                query = query.filter(Designation.academic_period_id == period_id)

        if teacher_ci is not None:
            query = query.filter(Designation.teacher_ci == teacher_ci)

        if status is not None:
            query = query.filter(Designation.status == status)

        designations = query.order_by(Designation.id).all()
        return [self._to_response(db, d) for d in designations]

    # ─── Get ──────────────────────────────────────────────────────────

    def get_designation(self, db: Session, designation_id: int) -> dict[str, Any]:
        """Get with slots, teacher, period details."""
        designation = self._get_or_404(db, designation_id)
        return self._to_response(db, designation)

    # ─── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _get_or_404(db: Session, designation_id: int) -> Designation:
        designation = db.query(Designation).filter(Designation.id == designation_id).first()
        if not designation:
            raise HTTPException(status_code=404, detail=f"Designación con id {designation_id} no encontrada")
        return designation

    @staticmethod
    def _to_response(
        db: Session,
        designation: Designation,
        created_slots: list[dict] | None = None,
        slot_errors: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Build response dict from designation."""
        # Get teacher name
        teacher = db.query(Teacher).filter(Teacher.ci == designation.teacher_ci).first()
        teacher_name = teacher.full_name if teacher else ""

        # Get slots
        if created_slots is None:
            slots = (
                db.query(DesignationSlot)
                .filter(DesignationSlot.designation_id == designation.id)
                .order_by(DesignationSlot.day_of_week, DesignationSlot.start_time)
                .all()
            )
            from app.scheduling.schemas.slot import DAY_NAMES
            from app.scheduling.models.room import Room

            slot_list = []
            for s in slots:
                room_code = ""
                if s.room_id:
                    room = db.query(Room).filter(Room.id == s.room_id).first()
                    room_code = room.code if room else ""
                slot_list.append({
                    "id": s.id,
                    "designation_id": s.designation_id,
                    "room_id": s.room_id,
                    "room_code": room_code,
                    "day_of_week": s.day_of_week,
                    "day_name": DAY_NAMES[s.day_of_week] if 0 <= s.day_of_week <= 6 else "",
                    "start_time": s.start_time.strftime("%H:%M") if s.start_time else "",
                    "end_time": s.end_time.strftime("%H:%M") if s.end_time else "",
                    "duration_minutes": s.duration_minutes,
                    "academic_hours": s.academic_hours,
                })
        else:
            slot_list = created_slots

        result: dict[str, Any] = {
            "id": designation.id,
            "teacher_ci": designation.teacher_ci,
            "teacher_name": teacher_name,
            "academic_period": designation.academic_period,
            "academic_period_id": designation.academic_period_id,
            "subject": designation.subject,
            "subject_id": designation.subject_id,
            "group_code": designation.group_code,
            "group_id": designation.group_id,
            "semester": designation.semester,
            "status": designation.status,
            "source": designation.source,
            "weekly_hours_calculated": designation.weekly_hours_calculated,
            "monthly_hours": designation.monthly_hours,
            "semester_hours": designation.semester_hours,
            "designation_type": designation.designation_type,
            "slots": slot_list,
        }

        if slot_errors:
            result["slot_errors"] = slot_errors

        return result


# ─── Legacy migration utility ────────────────────────────────────────


def migrate_legacy_designations(db: Session) -> dict[str, Any]:
    """Backfill FK columns for existing legacy designations.

    For each designation where academic_period_id is NULL:
    1. Match academic_period string -> AcademicPeriod.code -> set academic_period_id
    2. Match subject string -> Subject.name (exact) -> set subject_id
    3. Match group_code + period -> Group.code in that period -> set group_id
    4. Set source='legacy_import', status='confirmed'
    5. Parse schedule_json -> create DesignationSlot records

    Returns: {migrated: int, skipped: int, errors: list[str]}
    """
    from datetime import time as time_type

    DAY_MAP = {
        "lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2,
        "jueves": 3, "viernes": 4, "sabado": 5, "sábado": 5, "domingo": 6,
    }

    migrated = 0
    skipped = 0
    errors: list[str] = []

    # Build lookup caches
    period_map: dict[str, int] = {}
    for p in db.query(AcademicPeriod).all():
        period_map[p.code] = p.id

    subject_map: dict[str, int] = {}
    for s in db.query(Subject).all():
        subject_map[s.name.lower()] = s.id

    # Group lookup: (period_id, code) -> group_id
    group_map: dict[tuple[int, str], int] = {}
    for g in db.query(Group).all():
        group_map[(g.academic_period_id, g.code)] = g.id

    # Get designations that haven't been linked yet
    unlinked = (
        db.query(Designation)
        .filter(Designation.academic_period_id.is_(None))
        .all()
    )

    for desig in unlinked:
        try:
            # 1. Match period
            period_id = period_map.get(desig.academic_period)
            if not period_id:
                errors.append(f"Designation {desig.id}: period '{desig.academic_period}' not found in scheduling")
                skipped += 1
                continue

            desig.academic_period_id = period_id

            # 2. Match subject (exact, case-insensitive)
            subject_id = subject_map.get(desig.subject.lower())
            if subject_id:
                desig.subject_id = subject_id
            else:
                errors.append(f"Designation {desig.id}: subject '{desig.subject}' not found — FK left NULL")

            # 3. Match group
            group_id = group_map.get((period_id, desig.group_code))
            if group_id:
                desig.group_id = group_id
            else:
                errors.append(f"Designation {desig.id}: group '{desig.group_code}' in period {desig.academic_period} not found — FK left NULL")

            # 4. Set source/status
            desig.source = "legacy_import"
            if desig.status in (None, ""):
                desig.status = "confirmed"

            # 5. Parse schedule_json -> create DesignationSlot records (if none exist)
            existing_slots = (
                db.query(DesignationSlot)
                .filter(DesignationSlot.designation_id == desig.id)
                .count()
            )
            if existing_slots == 0 and desig.schedule_json:
                for entry in desig.schedule_json:
                    try:
                        dia = entry.get("dia", "").lower()
                        day_of_week = DAY_MAP.get(dia)
                        if day_of_week is None:
                            continue

                        h_inicio = entry.get("hora_inicio", "")
                        h_fin = entry.get("hora_fin", "")
                        if not h_inicio or not h_fin:
                            continue

                        parts_start = h_inicio.split(":")
                        parts_end = h_fin.split(":")
                        start = time_type(int(parts_start[0]), int(parts_start[1]))
                        end = time_type(int(parts_end[0]), int(parts_end[1]))

                        duration = entry.get("duracion_minutos", (end.hour * 60 + end.minute) - (start.hour * 60 + start.minute))
                        academic = entry.get("horas_academicas", max(1, round(duration / 45)))

                        slot = DesignationSlot(
                            designation_id=desig.id,
                            day_of_week=day_of_week,
                            start_time=start,
                            end_time=end,
                            duration_minutes=duration,
                            academic_hours=academic,
                        )
                        db.add(slot)
                    except Exception as slot_exc:
                        errors.append(f"Designation {desig.id}: slot parse error — {slot_exc}")

            migrated += 1

        except Exception as exc:
            errors.append(f"Designation {desig.id}: unexpected error — {exc}")
            skipped += 1

    db.flush()
    logger.info("Legacy migration: migrated=%d, skipped=%d, errors=%d", migrated, skipped, len(errors))

    return {"migrated": migrated, "skipped": skipped, "errors": errors}
