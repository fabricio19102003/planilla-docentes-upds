"""
Utility helpers for the Planilla Docentes UPDS system.
"""
from datetime import time, timedelta
from typing import Optional
import math


def parse_time_str(time_str: Optional[str]) -> Optional[time]:
    """
    Parse a time string in HH:MM or HH:MM:SS format to datetime.time.
    Returns None if input is None or empty.
    """
    if not time_str:
        return None
    try:
        parts = time_str.strip().split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(parts[2]) if len(parts) > 2 else 0
        return time(hour, minute, second)
    except (ValueError, AttributeError, IndexError):
        return None


def time_to_minutes(t: time) -> int:
    """Convert a datetime.time to total minutes since midnight."""
    return t.hour * 60 + t.minute


def minutes_to_time(minutes: int) -> time:
    """Convert total minutes since midnight to datetime.time."""
    hours = minutes // 60
    mins = minutes % 60
    return time(hours % 24, mins)


def add_minutes_to_time(t: time, minutes: int) -> time:
    """Add minutes to a time object. Handles day overflow."""
    total = time_to_minutes(t) + minutes
    return minutes_to_time(total % (24 * 60))


def calc_academic_hours(duration_minutes: int) -> int:
    """
    Calculate academic hours from duration in minutes.
    Formula: round(minutes / 45) per slot
    Validated against 399 designations in designaciones_normalizadas.json.
    """
    return round(duration_minutes / 45)


def normalize_group_code(raw_group: str) -> str:
    """
    Normalize group codes to standard format: M-1, T-2, N-3, G.E.
    """
    if not raw_group:
        return raw_group

    raw = raw_group.strip().upper()

    # G.E. pattern (Grupos Especiales)
    if "G.E" in raw or "GE" in raw or "G E" in raw:
        return "G.E."

    # Standard turn-number pattern
    turn_map = {"M": "M", "T": "T", "N": "N", "MAÑANA": "M", "TARDE": "T", "NOCHE": "N"}

    for prefix, turn in turn_map.items():
        if raw.startswith(prefix):
            # Extract number
            remainder = raw[len(prefix):].strip().strip("-").strip()
            if remainder.isdigit():
                return f"{turn}-{int(remainder)}"

    return raw_group  # Return as-is if no pattern matches
