"""
Service: App Settings

Provides read/write access to the ``app_settings`` key/value table.

Design
------
- Settings are read from the database on demand. Production runs multiple
  workers, so process-local caching would make authorization flags stale after
  an update handled by another worker.
- Typed getters (``get_active_academic_period``, ``get_hourly_rate`` …) wrap
  the raw ``get_setting`` call and apply safe defaults so callers don't have
  to know about the storage format.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.app_setting import AppSetting

logger = logging.getLogger(__name__)

# Well-known setting keys.  Keep in sync with the seed in ``main.py``.
KEY_ACTIVE_ACADEMIC_PERIOD = "ACTIVE_ACADEMIC_PERIOD"
KEY_COMPANY_NAME = "COMPANY_NAME"
KEY_COMPANY_NIT = "COMPANY_NIT"
KEY_HOURLY_RATE = "HOURLY_RATE"
KEY_PRACTICE_HOURLY_RATE = "PRACTICE_HOURLY_RATE"
KEY_DOCENTE_CAN_EDIT_PROFILE = "DOCENTE_CAN_EDIT_PROFILE"
KEY_DOCENTE_CAN_EDIT_PHOTO = "DOCENTE_CAN_EDIT_PHOTO"
KEY_MEDICINE_SCHEDULE_ASSISTANT_ENABLED = "MEDICINE_SCHEDULE_ASSISTANT_ENABLED"

# Safe defaults used when the row is missing (e.g. cache hit before seed, or
# a brand-new key introduced after the first deploy).
_DEFAULTS: dict[str, str] = {
    KEY_ACTIVE_ACADEMIC_PERIOD: "I/2026",
    KEY_COMPANY_NAME: "UNIPANDO S.R.L.",
    KEY_COMPANY_NIT: "456850023",
    KEY_HOURLY_RATE: "70.0",
    KEY_PRACTICE_HOURLY_RATE: "50.0",
    KEY_DOCENTE_CAN_EDIT_PROFILE: "false",
    KEY_DOCENTE_CAN_EDIT_PHOTO: "false",
    KEY_MEDICINE_SCHEDULE_ASSISTANT_ENABLED: "false",
}

# ── Generic accessors ──────────────────────────────────────────────────────


def get_setting(db: Session, key: str, default: str = "") -> str:
    """Return the raw string value for ``key`` or ``default`` if missing."""
    try:
        row = db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
    except Exception as exc:  # pragma: no cover - startup before table creation
        logger.warning("Could not read app setting %s: %s", key, exc)
        row = None
    if row is not None:
        return row.value
    return _DEFAULTS.get(key, default)


def get_all_settings(db: Session) -> dict[str, str]:
    """Return all current settings merged over safe defaults."""
    try:
        rows = db.query(AppSetting).all()
    except Exception as exc:  # pragma: no cover - startup before table creation
        logger.warning("Could not read app settings: %s", exc)
        rows = []
    # Merge defaults first so consumers always see all well-known keys.
    merged = dict(_DEFAULTS)
    merged.update({row.key: row.value for row in rows})
    return merged


def update_setting(
    db: Session,
    key: str,
    value: str,
    description: Optional[str] = None,
) -> AppSetting:
    """Upsert a single setting.  The caller is responsible for ``db.commit()``
    We flush so the value is visible within the same transaction.
    """
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if row:
        row.value = value
        if description is not None:
            row.description = description
    else:
        row = AppSetting(key=key, value=value, description=description)
        db.add(row)
    db.flush()
    return row


# ── Typed convenience getters ──────────────────────────────────────────────


def get_active_academic_period(db: Session) -> str:
    return get_setting(db, KEY_ACTIVE_ACADEMIC_PERIOD, _DEFAULTS[KEY_ACTIVE_ACADEMIC_PERIOD])


def get_company_name(db: Session) -> str:
    return get_setting(db, KEY_COMPANY_NAME, _DEFAULTS[KEY_COMPANY_NAME])


def get_company_nit(db: Session) -> str:
    return get_setting(db, KEY_COMPANY_NIT, _DEFAULTS[KEY_COMPANY_NIT])


def get_hourly_rate(db: Session) -> float:
    raw = get_setting(db, KEY_HOURLY_RATE, _DEFAULTS[KEY_HOURLY_RATE])
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid HOURLY_RATE value in DB: %r — falling back to default", raw)
        return float(_DEFAULTS[KEY_HOURLY_RATE])


def get_practice_hourly_rate(db: Session) -> float:
    """Tarifa por hora académica para docentes asistenciales (prácticas internas)."""
    raw = get_setting(db, KEY_PRACTICE_HOURLY_RATE, _DEFAULTS[KEY_PRACTICE_HOURLY_RATE])
    try:
        return float(raw)
    except (TypeError, ValueError):
        logger.warning("Invalid PRACTICE_HOURLY_RATE value in DB: %r — falling back to default", raw)
        return float(_DEFAULTS[KEY_PRACTICE_HOURLY_RATE])


def _parse_bool(raw: str, default: bool = False) -> bool:
    value = (raw or "").strip().lower()
    if value in {"true", "1", "yes", "y", "on"}:
        return True
    if value in {"false", "0", "no", "n", "off"}:
        return False
    logger.warning("Invalid boolean app setting value: %r — falling back to %s", raw, default)
    return default


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def get_docente_can_edit_profile(db: Session) -> bool:
    raw = get_setting(db, KEY_DOCENTE_CAN_EDIT_PROFILE, _DEFAULTS[KEY_DOCENTE_CAN_EDIT_PROFILE])
    return _parse_bool(raw, default=False)


def get_docente_can_edit_photo(db: Session) -> bool:
    raw = get_setting(db, KEY_DOCENTE_CAN_EDIT_PHOTO, _DEFAULTS[KEY_DOCENTE_CAN_EDIT_PHOTO])
    return _parse_bool(raw, default=False)


def get_medicine_schedule_assistant_enabled(db: Session) -> bool:
    raw = get_setting(db, KEY_MEDICINE_SCHEDULE_ASSISTANT_ENABLED,
                      _DEFAULTS[KEY_MEDICINE_SCHEDULE_ASSISTANT_ENABLED])
    return _parse_bool(raw, default=False)


def set_docente_can_edit_profile(db: Session, value: bool) -> AppSetting:
    return update_setting(db, KEY_DOCENTE_CAN_EDIT_PROFILE, _format_bool(value))


def set_docente_can_edit_photo(db: Session, value: bool) -> AppSetting:
    return update_setting(db, KEY_DOCENTE_CAN_EDIT_PHOTO, _format_bool(value))


def set_medicine_schedule_assistant_enabled(db: Session, value: bool) -> AppSetting:
    return update_setting(db, KEY_MEDICINE_SCHEDULE_ASSISTANT_ENABLED, _format_bool(value))
