"""
Service: App Settings

Provides cached read/write access to the ``app_settings`` key/value table.

Design
------
- An in-memory cache is populated on first access and invalidated on every
  update.  The cache lives for the lifetime of the worker process — in
  development (uvicorn --reload) or a single-worker deployment this is fine.
  With multiple workers, each worker holds its own cache; writes in worker A
  won't be seen by worker B until its cache expires (today only on restart).
  If we ever move to multi-worker deployments we'll need an event bus or
  per-request read — this is documented here so it's not a surprise.
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

# Safe defaults used when the row is missing (e.g. cache hit before seed, or
# a brand-new key introduced after the first deploy).
_DEFAULTS: dict[str, str] = {
    KEY_ACTIVE_ACADEMIC_PERIOD: "I/2026",
    KEY_COMPANY_NAME: "UNIPANDO S.R.L.",
    KEY_COMPANY_NIT: "456850023",
    KEY_HOURLY_RATE: "70.0",
    KEY_PRACTICE_HOURLY_RATE: "50.0",
}

# ── In-memory cache ────────────────────────────────────────────────────────
# Module-level state is intentional: a single cache shared by all requests
# handled by this worker process.
_cache: dict[str, str] = {}
_cache_loaded = False


def _ensure_cache(db: Session) -> None:
    global _cache, _cache_loaded
    if _cache_loaded:
        return
    try:
        rows = db.query(AppSetting).all()
    except Exception as exc:  # pragma: no cover - defensive
        # If the table doesn't exist yet (very first startup before seeding)
        # don't crash; fall back to defaults.  Leave _cache_loaded = False so
        # the next call retries instead of caching an empty dict permanently.
        logger.warning("Could not load app_settings cache: %s", exc)
        return
    _cache = {r.key: r.value for r in rows}
    _cache_loaded = True
    logger.debug("app_settings cache loaded (%d keys)", len(_cache))


def invalidate_cache() -> None:
    """Drop the in-memory cache.  Call after any write."""
    global _cache, _cache_loaded
    _cache = {}
    _cache_loaded = False


# ── Generic accessors ──────────────────────────────────────────────────────


def get_setting(db: Session, key: str, default: str = "") -> str:
    """Return the raw string value for ``key`` or ``default`` if missing."""
    _ensure_cache(db)
    if key in _cache:
        return _cache[key]
    return _DEFAULTS.get(key, default)


def get_all_settings(db: Session) -> dict[str, str]:
    """Return a shallow copy of the current cache (for diagnostics)."""
    _ensure_cache(db)
    # Merge defaults first so consumers always see all well-known keys.
    merged = dict(_DEFAULTS)
    merged.update(_cache)
    return merged


def update_setting(
    db: Session,
    key: str,
    value: str,
    description: Optional[str] = None,
) -> AppSetting:
    """Upsert a single setting.  The caller is responsible for ``db.commit()``
    and for calling ``invalidate_cache()`` **after** the commit succeeds.

    We flush so the value is visible within the same transaction but do NOT
    invalidate the cache here — that must happen after the commit to prevent
    a race where another request re-populates the cache from stale committed
    data between flush and commit.
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
