from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from app.models.attendance import AttendanceRecord


@dataclass(frozen=True)
class AttendanceSourceDetails:
    source_kind: Literal["legacy", "published"]
    source_id: int
    designation_id: int | None
    published_schedule_assignment_id: int | None
    subject: str
    group_code: str
    semester: str
    activity_type: str

    @property
    def source_key(self) -> str:
        return f"{self.source_kind}:{self.source_id}"


@dataclass(frozen=True)
class AttendanceScheduleSnapshot:
    source_kind: Literal["legacy", "published"]
    source_id: int
    designation_id: int | None
    published_schedule_assignment_id: int | None
    subject: str
    group_code: str
    semester: str
    activity_type: str
    monthly_hours: int
    weekly_hours: int
    schedule_json: tuple[dict[str, object], ...]

    @property
    def source_key(self) -> str:
        return f"{self.source_kind}:{self.source_id}"


def attendance_source_details(record: AttendanceRecord) -> AttendanceSourceDetails:
    if record.designation_id is not None:
        designation = record.designation
        if designation is None:
            raise ValueError(f"Legacy attendance {record.id} has no designation")
        return AttendanceSourceDetails(
            source_kind="legacy",
            source_id=designation.id,
            designation_id=designation.id,
            published_schedule_assignment_id=None,
            subject=designation.subject,
            group_code=designation.group_code,
            semester=str(designation.semester),
            activity_type="practice" if designation.designation_type == "practice" else "theory",
        )

    assignment = record.published_schedule_assignment
    if assignment is None:
        raise ValueError(f"Published attendance {record.id} has no immutable assignment snapshot")
    block = assignment.block
    return AttendanceSourceDetails(
        source_kind="published",
        source_id=assignment.id,
        designation_id=None,
        published_schedule_assignment_id=assignment.id,
        subject=block.subject_name,
        group_code=block.group_code,
        semester=str(block.semester),
        activity_type=block.activity_type,
    )


def attendance_schedule_snapshots(
    records: Iterable[AttendanceRecord],
) -> list[AttendanceScheduleSnapshot]:
    """Reconstruct historical schedule context only from persisted attendance provenance."""
    weekday_names = (
        "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
    )
    grouped: dict[str, dict[str, object]] = {}
    for record in records:
        source = attendance_source_details(record)
        duration_minutes = (
            record.scheduled_end.hour * 60 + record.scheduled_end.minute
            - record.scheduled_start.hour * 60 - record.scheduled_start.minute
        )
        slot_hours = max(1, duration_minutes // 45)
        group = grouped.setdefault(source.source_key, {
            "source": source,
            "monthly_hours": 0,
            "slots": {},
        })
        group["monthly_hours"] = int(group["monthly_hours"]) + slot_hours
        slot = {
            "dia": weekday_names[record.date.weekday()],
            "hora_inicio": record.scheduled_start.strftime("%H:%M"),
            "hora_fin": record.scheduled_end.strftime("%H:%M"),
            "horas_academicas": slot_hours,
        }
        slots = group["slots"]
        assert isinstance(slots, dict)
        slots[(slot["dia"], slot["hora_inicio"], slot["hora_fin"])] = slot

    snapshots: list[AttendanceScheduleSnapshot] = []
    for group in grouped.values():
        source = group["source"]
        assert isinstance(source, AttendanceSourceDetails)
        raw_slots = group["slots"]
        assert isinstance(raw_slots, dict)
        slots = tuple(raw_slots[key] for key in sorted(raw_slots))
        snapshots.append(AttendanceScheduleSnapshot(
            source_kind=source.source_kind,
            source_id=source.source_id,
            designation_id=source.designation_id,
            published_schedule_assignment_id=source.published_schedule_assignment_id,
            subject=source.subject,
            group_code=source.group_code,
            semester=source.semester,
            activity_type=source.activity_type,
            monthly_hours=int(group["monthly_hours"]),
            weekly_hours=sum(int(slot["horas_academicas"]) for slot in slots),
            schedule_json=slots,
        ))
    return sorted(snapshots, key=lambda item: (item.subject.casefold(), item.group_code, item.source_key))
