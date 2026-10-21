"""Parse free-text UPDS schedule cells into academic schedule slots.

A cell lists one or more ``DAY: start - end`` segments, separated by newlines, slashes or plain
spaces. Real workbooks mix 12-hour and 24-hour notation (``13: 40 pm``), drop the colon
between hour and minutes (``08 10 am``) and contain typos. Every segment either becomes a
slot or produces one error message naming the segment, so callers can reject the row
instead of silently losing a class.
"""
from __future__ import annotations

import re
import unicodedata

from app.utils.helpers import calc_academic_hours

MAX_SLOT_MINUTES = 6 * 60

_DAY_NAMES = {
    "LUNES": "lunes", "LUNE": "lunes",
    "MARTES": "martes", "MARTE": "martes",
    "MIERCOLES": "miercoles", "MIERCOLE": "miercoles",
    "JUEVES": "jueves", "JUVES": "jueves", "JEVES": "jueves",
    "VIERNES": "viernes", "VIERNE": "viernes",
    "SABADO": "sabado", "SABDO": "sabado",
    "DOMINGO": "domingo",
}
_DAY_RE = re.compile(r"\b(" + "|".join(sorted(_DAY_NAMES, key=len, reverse=True)) + r")\b\s*:?")
_CLOCK = r"(\d{1,2})\s*[:.\s]\s*(\d{2})\s*:?\s*(AM|PM)?"
_RANGE_RE = re.compile(rf"^{_CLOCK}\s*(?:-+|\bA\b)\s*{_CLOCK}$")
_TRAILING_UNIT_RE = re.compile(r"\s*\b(?:HRS?|HS|HORAS)\b\.?$")


def _fold(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.upper())
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _valid_clock(hour: int, minute: int) -> bool:
    return hour <= 23 and minute <= 59


def _to_minutes(hour: int, minute: int, marker: str | None) -> int | None:
    """Return minutes since midnight, or None when the AM/PM marker contradicts the hour."""
    if marker is None or hour > 12:
        # 24-hour value; a PM marker on 13..23 is redundant, an AM marker is contradictory.
        if marker == "AM" and hour > 12:
            return None
        return hour * 60 + minute
    if hour == 0:
        return None
    hour = hour % 12 + (12 if marker == "PM" else 0)
    return hour * 60 + minute


def _format(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_schedule_text(raw: str | None) -> tuple[list[dict], list[str]]:
    """Return ``(slots, errors)`` for a schedule cell.

    Slots use the internal ``schedule_json`` shape. A blank cell yields no slots and no
    errors; the caller decides whether a schedule is required.
    """
    text = str(raw or "").strip()
    if not text:
        return [], []
    folded = _fold(text).replace("´", "").replace("`", "")
    days = list(_DAY_RE.finditer(folded))
    if not days:
        return [], [f"No se encontró ningún día en el horario: {text!r}"]

    slots: list[dict] = []
    errors: list[str] = []
    leading = folded[:days[0].start()].strip(" \t\n;,")
    if leading:
        errors.append(f"Texto sin día en el horario: {leading!r}")

    for index, day in enumerate(days):
        end = days[index + 1].start() if index + 1 < len(days) else len(folded)
        segment = " ".join(folded[day.end():end].split()).strip(" ;,/")
        segment = _TRAILING_UNIT_RE.sub("", segment).rstrip(" .;,/")
        label = f"{day.group(1)}: {segment}"
        match = _RANGE_RE.match(segment)
        if not match:
            errors.append(f"No se pudo leer el bloque {label!r}")
            continue
        h1, m1, mark1, h2, m2, mark2 = match.groups()
        h1, m1, h2, m2 = int(h1), int(m1), int(h2), int(m2)
        if not (_valid_clock(h1, m1) and _valid_clock(h2, m2)):
            errors.append(f"El bloque {label!r} tiene una hora inválida")
            continue
        if mark1 is None and mark2 is not None and h1 <= 12 and h2 <= 12:
            # "03:00-05:00 PM": the trailing marker also applies to the start when that
            # keeps the block in chronological order.
            end_minutes = _to_minutes(h2, m2, mark2)
            start_minutes = _to_minutes(h1, m1, mark2)
            if start_minutes is None or end_minutes is None or start_minutes >= end_minutes:
                start_minutes = _to_minutes(h1, m1, None)
        else:
            start_minutes = _to_minutes(h1, m1, mark1)
            end_minutes = _to_minutes(h2, m2, mark2)
        if start_minutes is None or end_minutes is None:
            errors.append(f"AM/PM contradictorio en el bloque {label!r}")
            continue
        if end_minutes <= start_minutes:
            errors.append(f"El bloque {label!r} termina antes de empezar")
            continue
        duration = end_minutes - start_minutes
        if duration > MAX_SLOT_MINUTES:
            errors.append(f"El bloque {label!r} dura más de 6 horas")
            continue
        slots.append({
            "dia": _DAY_NAMES[day.group(1)],
            "hora_inicio": _format(start_minutes),
            "hora_fin": _format(end_minutes),
            "duracion_minutos": duration,
            "horas_academicas": calc_academic_hours(duration),
        })
    return slots, errors
