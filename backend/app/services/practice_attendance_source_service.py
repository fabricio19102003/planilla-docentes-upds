from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.practice_attendance import PracticeAttendanceLog


@dataclass(frozen=True)
class PracticeAttendanceSourceDetails:
    source_kind: Literal["legacy", "published"]
    source_id: int
    designation_id: int | None
    published_schedule_assignment_id: int | None
    subject: str
    group_code: str
    semester: str
    activity_type: Literal["practice"] = "practice"

    @property
    def source_key(self) -> str:
        return f"{self.source_kind}:{self.source_id}"


def practice_attendance_source_details(
    record: PracticeAttendanceLog,
) -> PracticeAttendanceSourceDetails:
    if record.designation_id is not None:
        designation = record.designation
        if designation is None:
            raise ValueError(f"Legacy practice attendance {record.id} has no designation")
        return PracticeAttendanceSourceDetails(
            source_kind="legacy",
            source_id=designation.id,
            designation_id=designation.id,
            published_schedule_assignment_id=None,
            subject=designation.subject,
            group_code=designation.group_code,
            semester=str(designation.semester),
        )
    assignment = record.published_schedule_assignment
    if assignment is None:
        raise ValueError(f"Published practice attendance {record.id} has no immutable assignment")
    block = assignment.block
    return PracticeAttendanceSourceDetails(
        source_kind="published",
        source_id=assignment.id,
        designation_id=None,
        published_schedule_assignment_id=assignment.id,
        subject=block.subject_name,
        group_code=block.group_code,
        semester=str(block.semester),
    )
