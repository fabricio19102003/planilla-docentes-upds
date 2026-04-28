from datetime import time
from typing import Iterable


class SchedulingConflictService:
    @staticmethod
    def normalize_time(value: time | str) -> time | None:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                from datetime import datetime
                return datetime.strptime(value, "%H:%M").time()
            except ValueError:
                return None
        return value

    @staticmethod
    def has_overlap(existing_slots: Iterable[dict], candidate: dict) -> bool:
        candidate_start = SchedulingConflictService.normalize_time(candidate.get("hora_inicio"))
        candidate_end = SchedulingConflictService.normalize_time(candidate.get("hora_fin"))
        if candidate_start is None or candidate_end is None:
            return False

        for slot in existing_slots:
            start = SchedulingConflictService.normalize_time(slot.get("hora_inicio"))
            end = SchedulingConflictService.normalize_time(slot.get("hora_fin"))
            if start is None or end is None:
                continue
            if candidate_start < end and candidate_end > start:
                return True

        return False

    @staticmethod
    def detect_teacher_conflicts(slots: list[dict]) -> list[str]:
        problems: list[str] = []
        days: dict[str, list[dict]] = {}
        for slot in slots:
            day = (slot.get("dia") or "").strip().lower()
            if not day:
                continue
            days.setdefault(day, []).append(slot)

        for day, day_slots in days.items():
            for index, slot in enumerate(day_slots):
                later = day_slots[index + 1 :]
                if SchedulingConflictService.has_overlap(later, slot):
                    problems.append(
                        f"Conflicting slots on {day}: {slot.get('hora_inicio')} - {slot.get('hora_fin')}"
                    )
        return problems
