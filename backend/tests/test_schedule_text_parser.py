"""Schedule text parsing used by the designation loader and importer.

Every case comes from real II/2026 designation workbook cells; teacher data is omitted.
"""
from __future__ import annotations

import pytest

from app.services.designation_loader import DesignationLoader


def _slots(raw: str) -> list[tuple[str, str, str, int]]:
    return [
        (slot["dia"], slot["hora_inicio"], slot["hora_fin"], slot["horas_academicas"])
        for slot in DesignationLoader._parse_horario_string(raw)
    ]


def _strict(raw: str):
    return DesignationLoader.parse_horario_with_errors(raw)


class TestAcceptedSchedules:
    def test_24h_hours_with_redundant_pm_marker(self):
        raw = "Martes: 13: 40 pm- 15: 10 pm\nMiercoles: 13: 40 pm- 15: 10 pm\nJueves: 13: 40 pm- 16: 05 pm"
        assert _slots(raw) == [
            ("martes", "13:40", "15:10", 2),
            ("miercoles", "13:40", "15:10", 2),
            ("jueves", "13:40", "16:05", 3),
        ]

    def test_12h_morning_schedule_is_preserved(self):
        raw = "Lunes: 06: 30 am- 08: 55 am\nMartes: 06: 30 am- 08: 00 am"
        assert _slots(raw) == [("lunes", "06:30", "08:55", 3), ("martes", "06:30", "08:00", 2)]

    def test_noon_pm_is_midday(self):
        assert _slots("Lunes: 12: 00 pm- 13: 30 pm") == [("lunes", "12:00", "13:30", 2)]

    def test_morning_to_afternoon_mixed_notation(self):
        assert _slots("Lunes: 11:10 am- 14: 00 pm") == [("lunes", "11:10", "14:00", 4)]

    def test_several_days_on_one_line(self):
        raw = "Miercoles: 11: 20 am- 12: 00 pm               Jueves: 10: 35 am- 12: 00 pm"
        assert _slots(raw) == [("miercoles", "11:20", "12:00", 1), ("jueves", "10:35", "12:00", 2)]

    def test_hour_and_minute_separated_by_space(self):
        assert _slots("Miercoles: 08 10 am- 10: 35 am") == [("miercoles", "08:10", "10:35", 3)]

    def test_marker_glued_to_minutes_and_double_hyphen(self):
        assert _slots("Martes: 20: 50 pm- 23: 05pm\nViernes: 15: 10 pm-- 17: 25 pm") == [
            ("martes", "20:50", "23:05", 3),
            ("viernes", "15:10", "17:25", 3),
        ]

    def test_existing_24h_formats_still_parse(self):
        raw = "LUNES 06:30 - 08:00\n MARTES 15:10-17:25\n JUVES: 15:55-17:25\nVIERNES 17:30-18.15"
        assert _slots(raw) == [
            ("lunes", "06:30", "08:00", 2),
            ("martes", "15:10", "17:25", 3),
            ("jueves", "15:55", "17:25", 2),
            ("viernes", "17:30", "18:15", 1),
        ]

    def test_trailing_pm_applies_to_both_ends_when_order_allows(self):
        assert _slots("LUNES 03:00-05:00 PM") == [("lunes", "15:00", "17:00", 3)]

    def test_day_name_split_from_time_line(self):
        assert _slots("Jueves\n20:50 - 23:00") == [("jueves", "20:50", "23:00", 3)]

    def test_letter_a_as_separator(self):
        assert _slots("MARTES 16:05 A 17:35") == [("martes", "16:05", "17:35", 2)]

    def test_blank_schedule_has_no_slots_and_no_errors(self):
        assert _strict("") == ([], [])


class TestRejectedSchedules:
    @pytest.mark.parametrize(
        "raw",
        [
            "Martes: 08: 55 am- 11: 20 pm",   # 14 h 25 min in one block
            "Jueves: 06: 30 am- 08: 00 pm",   # 13 h 30 min in one block
        ],
    )
    def test_block_longer_than_six_hours_is_rejected(self, raw):
        slots, errors = _strict(raw)
        assert slots == []
        assert len(errors) == 1
        assert "más de 6 horas" in errors[0]

    @pytest.mark.parametrize(
        "raw",
        [
            "Jueves: 19: 30 pm- 18: 15 pm",   # ends before it starts
            "Viernes: 09: 50 am- 12:05 am",   # 12:05 am is just after midnight
            "Miercoles: 11: 10 pm- 12: 40 pm",
        ],
    )
    def test_block_ending_before_start_is_rejected(self, raw):
        slots, errors = _strict(raw)
        assert slots == []
        assert len(errors) == 1
        assert "termina antes de empezar" in errors[0]

    def test_am_marker_on_24h_hour_is_ambiguous(self):
        slots, errors = _strict("Miercoles: 20: 50 am- 23: 05 pm")
        assert slots == []
        assert len(errors) == 1
        assert "AM/PM" in errors[0]

    @pytest.mark.parametrize(
        "raw",
        [
            "Viernes: 19: 10n pm- 19: 55 pm",
            "Martes: 22: 20 pm: 23: 05",
            "Martes: 12: 40 pm- 14: 10 ´pm extra",
        ],
    )
    def test_unreadable_segment_is_reported(self, raw):
        slots, errors = _strict(raw)
        assert slots == []
        assert len(errors) == 1
        assert raw.split(":")[0].strip().upper() in errors[0].upper()

    def test_one_bad_day_keeps_the_valid_day_and_reports_the_bad_one(self):
        slots, errors = _strict("Lunes: 06:30 am- 08:00 am\nJueves: 06: 30 am- 08: 00 pm")
        assert [(s["dia"], s["hora_inicio"], s["hora_fin"]) for s in slots] == [("lunes", "06:30", "08:00")]
        assert len(errors) == 1
        assert "JUEVES" in errors[0].upper()

    def test_text_without_any_day_is_reported(self):
        slots, errors = _strict("06:30 - 08:00")
        assert slots == []
        assert errors == ["No se encontró ningún día en el horario: '06:30 - 08:00'"]


class TestLegacyNotationsKept:
    def test_trailing_hrs_and_period_are_ignored(self):
        assert _slots("LUNES 08:00 - 10:00 hrs\nMARTES 08:00-10:00.") == [
            ("lunes", "08:00", "10:00", 3),
            ("martes", "08:00", "10:00", 3),
        ]

    def test_slash_between_blocks(self):
        assert _slots("LUNES 08:00-09:30 / MIERCOLES 08:00-09:30") == [
            ("lunes", "08:00", "09:30", 2),
            ("miercoles", "08:00", "09:30", 2),
        ]

    def test_sunday_is_a_valid_day(self):
        assert _slots("DOMINGO 08:00-09:30") == [("domingo", "08:00", "09:30", 2)]

    @pytest.mark.parametrize("raw", ["LUNES 22:00-24:00", "LUNES 08:70-09:30"])
    def test_impossible_clock_time_reports_invalid_time(self, raw):
        slots, errors = _strict(raw)
        assert slots == []
        assert len(errors) == 1
        assert "hora inválida" in errors[0]
        assert "AM/PM" not in errors[0]
