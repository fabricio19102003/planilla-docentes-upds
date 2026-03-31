"""
Service: Designation Loader
Loads designaciones_normalizadas.json into the database.

Strategy for teacher CI resolution:
  - Designations don't have CI → create teachers with TEMP-{slug} CI
  - When biometric data arrives (CI + name), call link_teachers_by_name()
    to promote TEMP records to real CIs using fuzzy name matching
"""
from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import and_, exists, select
from sqlalchemy.orm import Session, aliased

from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricRecord
from app.models.designation import Designation
from app.models.teacher import Teacher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class DesignationLoadResult:
    teachers_created: int = 0
    teachers_reused: int = 0
    designations_loaded: int = 0
    skipped_no_schedule: int = 0
    skipped_no_time: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def total_skipped(self) -> int:
        return self.skipped_no_schedule + self.skipped_no_time

    def __str__(self) -> str:
        return (
            f"DesignationLoadResult("
            f"teachers_created={self.teachers_created}, "
            f"teachers_reused={self.teachers_reused}, "
            f"designations_loaded={self.designations_loaded}, "
            f"skipped={self.total_skipped}, "
            f"warnings={len(self.warnings)})"
        )


# ---------------------------------------------------------------------------
# Name normalisation helpers
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Uppercase, strip accents/diacritics, collapse whitespace."""
    nfkd = unicodedata.normalize("NFD", name)
    stripped = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return " ".join(stripped.upper().split())


def names_match(name1: str, name2: str) -> bool:
    """
    Return True if two names likely refer to the same person.

    Strategies (in order):
    1. Exact match after normalization.
    2. One name is a substring of the other (handles abbreviations).
    3. At least 2 tokens in common (handles different orderings / middle names).
    """
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    if n1 == n2:
        return True

    if n1 in n2 or n2 in n1:
        return True

    tokens1 = set(n1.split())
    tokens2 = set(n2.split())
    common = tokens1 & tokens2
    return len(common) >= 2


def _make_temp_ci(full_name: str) -> str:
    """
    Generate a deterministic TEMP CI from a teacher name.

    Format: TEMP-{8-char hex digest of normalised name}
    Max length: 13 chars — fits inside String(20).
    """
    normalised = normalize_name(full_name)
    digest = hashlib.sha256(normalised.encode()).hexdigest()[:8]
    return f"TEMP-{digest}"


# ---------------------------------------------------------------------------
# Main loader class
# ---------------------------------------------------------------------------

class DesignationLoader:
    """Loads normalized designation JSON into the database."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_from_json(
        self,
        db: Session,
        json_path: str,
    ) -> DesignationLoadResult:
        """
        Load designations from designaciones_normalizadas.json.

        Steps
        -----
        1. Read and validate JSON file.
        2. For each designation entry:
           a. Skip entries without schedule (prácticas clínicas sin docente).
           b. Create or reuse a Teacher row using a TEMP CI derived from the name.
           c. Create a Designation row with schedule_json.
        3. Commit the session and return load statistics.
        """
        result = DesignationLoadResult()
        path = Path(json_path)

        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {json_path}")

        with path.open(encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)

        entries: list[dict[str, Any]] = data.get("designaciones", [])
        logger.info("Read %d designation entries from %s", len(entries), path.name)

        # Cache of name → TEMP CI to avoid repeated DB lookups within this run
        name_to_ci: dict[str, str] = {}

        for entry in entries:
            docente_raw = entry.get("docente")
            horario: list[dict] = entry.get("horario") or []

            # ---- Skip: no schedule ----
            if not horario:
                if not docente_raw:
                    # Prácticas clínicas sin docente asignado
                    result.skipped_no_schedule += 1
                    logger.debug("Skipped entry without docente or schedule: %s", entry.get("materia"))
                else:
                    # Docente exists but no schedule slots (skipped_no_time)
                    result.skipped_no_time += 1
                    result.warnings.append(
                        f"Sin horario para docente '{docente_raw}' — materia '{entry.get('materia')}'"
                    )
                continue

            # ---- Skip: has schedule but docente is null ----
            if not docente_raw:
                result.skipped_no_schedule += 1
                logger.debug(
                    "Skipped entry with schedule but no docente: %s %s",
                    entry.get("materia"),
                    entry.get("grupo"),
                )
                continue

            docente_name: str = docente_raw.strip()
            if not docente_name:
                result.skipped_no_schedule += 1
                continue

            # ---- Resolve or create Teacher ----
            teacher_ci = self._get_or_create_teacher(
                db=db,
                full_name=docente_name,
                name_to_ci_cache=name_to_ci,
                result=result,
            )

            subject = entry.get("materia", "")
            semester = entry.get("semestre", "")
            group_code = entry.get("grupo", "")

            # ---- Create or update Designation ----
            designation = (
                db.query(Designation)
                .filter(
                    Designation.teacher_ci == teacher_ci,
                    Designation.subject == subject,
                    Designation.semester == semester,
                    Designation.group_code == group_code,
                )
                .first()
            )

            if designation is None:
                designation = Designation(
                    teacher_ci=teacher_ci,
                    subject=subject,
                    semester=semester,
                    group_code=group_code,
                    schedule_json=horario,
                    semester_hours=entry.get("carga_horaria_semestral"),
                    monthly_hours=entry.get("carga_horaria_mensual"),
                    weekly_hours=entry.get("carga_horaria_semanal"),
                    weekly_hours_calculated=entry.get("total_horas_academicas_semanal_calculado"),
                    schedule_raw=entry.get("horario_raw"),
                )
                db.add(designation)
            else:
                designation.schedule_json = horario
                designation.semester_hours = entry.get("carga_horaria_semestral")
                designation.monthly_hours = entry.get("carga_horaria_mensual")
                designation.weekly_hours = entry.get("carga_horaria_semanal")
                designation.weekly_hours_calculated = entry.get("total_horas_academicas_semanal_calculado")
                designation.schedule_raw = entry.get("horario_raw")

            result.designations_loaded += 1

        db.commit()

        logger.info(
            "Load complete — teachers_created=%d, reused=%d, designations=%d, skipped=%d, warnings=%d",
            result.teachers_created,
            result.teachers_reused,
            result.designations_loaded,
            result.total_skipped,
            len(result.warnings),
        )
        return result

    def load_from_excel(
        self,
        db: Session,
        excel_path: str,
    ) -> DesignationLoadResult:
        """
        Alternative entry point: parse the Excel directly.

        For now, delegates to load_from_json with the pre-parsed JSON file
        located next to the excel (or in the project root).
        """
        excel_p = Path(excel_path)
        # Convention: JSON lives next to the Excel with a fixed name
        json_path = excel_p.parent / "designaciones_normalizadas.json"
        logger.info(
            "load_from_excel called — delegating to load_from_json (%s)", json_path
        )
        return self.load_from_json(db=db, json_path=str(json_path))

    def link_teachers_by_name(
        self,
        db: Session,
        ci_name_map: dict[str, str],
    ) -> int:
        """
        Promote TEMP CI teachers to real CIs using biometric data.

        Parameters
        ----------
        ci_name_map : dict[str, str]
            Mapping  ``{ci: full_name}``  obtained from the biometric parser.

        Returns
        -------
        int
            Number of teachers whose CI was successfully updated.

        Algorithm
        ---------
        For each TEMP teacher (CI starts with "TEMP-"):
          1. Search ci_name_map for a name that passes ``names_match()``.
          2. If found:
             a. Update Teacher.ci = real_ci  (and full_name if empty).
             b. Cascade-update Designation.teacher_ci via ORM relationship.
          3. If not found: leave as TEMP and log a warning.
        """
        temp_teachers: list[Teacher] = (
            db.query(Teacher)
            .filter(Teacher.ci.like("TEMP-%"))
            .all()
        )

        if not temp_teachers:
            logger.info("link_teachers_by_name: no TEMP teachers found — nothing to do")
            return 0

        updated = 0

        try:
            for teacher in temp_teachers:
                matched_ci: str | None = None
                matched_name: str | None = None

                for real_ci, real_name in ci_name_map.items():
                    if names_match(teacher.full_name, real_name):
                        matched_ci = real_ci
                        matched_name = real_name
                        break

                if matched_ci is None:
                    logger.warning(
                        "link_teachers_by_name: no match for TEMP teacher '%s' (%s)",
                        teacher.full_name,
                        teacher.ci,
                    )
                    continue

                existing = db.query(Teacher).filter(Teacher.ci == matched_ci).first()
                if existing:
                    logger.info(
                        "Real CI %s already in DB — merging designations from %s",
                        matched_ci,
                        teacher.ci,
                    )
                    self._merge_temp_teacher_into_existing(
                        db=db,
                        temp_teacher=teacher,
                        real_teacher=existing,
                    )
                else:
                    old_ci = teacher.ci

                    db.query(AttendanceRecord).filter(
                        AttendanceRecord.teacher_ci == old_ci
                    ).update({"teacher_ci": matched_ci}, synchronize_session=False)
                    db.query(BiometricRecord).filter(
                        BiometricRecord.teacher_ci == old_ci
                    ).update({"teacher_ci": matched_ci}, synchronize_session=False)
                    db.query(Designation).filter(
                        Designation.teacher_ci == old_ci
                    ).update({"teacher_ci": matched_ci}, synchronize_session=False)

                    teacher.ci = matched_ci  # type: ignore[assignment]
                    if matched_name:
                        teacher.full_name = matched_name

                updated += 1
                logger.info(
                    "Linked '%s': %s → %s", teacher.full_name, teacher.ci, matched_ci
                )

            db.commit()
        except Exception:
            db.rollback()
            raise

        logger.info("link_teachers_by_name: updated %d teachers", updated)
        return updated

    def get_teacher_designations(
        self,
        db: Session,
        teacher_ci: str,
    ) -> list[Designation]:
        """Return all Designation rows for a given teacher CI."""
        return (
            db.query(Designation)
            .filter(Designation.teacher_ci == teacher_ci)
            .all()
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_or_create_teacher(
        self,
        db: Session,
        full_name: str,
        name_to_ci_cache: dict[str, str],
        result: DesignationLoadResult,
    ) -> str:
        """
        Return the CI for a teacher, creating a TEMP record if necessary.

        Uses an in-memory cache keyed by normalised name so that multiple
        designations for the same teacher don't cause redundant DB hits or
        duplicate inserts within a single load run.
        """
        normalised = normalize_name(full_name)
        temp_ci = _make_temp_ci(full_name)

        if normalised in name_to_ci_cache:
            result.teachers_reused += 1
            return name_to_ci_cache[normalised]

        existing_by_name = self._find_teacher_by_normalized_name(db, normalised)
        if existing_by_name is not None:
            if not existing_by_name.ci.startswith("TEMP-") and existing_by_name.ci != temp_ci:
                warning = (
                    f"Posible homónimo: '{full_name}' reutiliza CI real '{existing_by_name.ci}' "
                    f"en lugar de TEMP '{temp_ci}'"
                )
                logger.warning(warning)
                result.warnings.append(warning)
            result.teachers_reused += 1
            name_to_ci_cache[normalised] = existing_by_name.ci
            return existing_by_name.ci

        # Check DB (in case a previous load already inserted this teacher)
        existing = db.query(Teacher).filter(Teacher.ci == temp_ci).first()
        if existing:
            result.teachers_reused += 1
            name_to_ci_cache[normalised] = temp_ci
            return temp_ci

        # Create new TEMP teacher
        teacher = Teacher(ci=temp_ci, full_name=full_name)
        db.add(teacher)
        db.flush()  # assign PK without committing the transaction

        result.teachers_created += 1
        name_to_ci_cache[normalised] = temp_ci
        logger.debug("Created TEMP teacher: ci=%s name='%s'", temp_ci, full_name)
        return temp_ci

    def _find_teacher_by_normalized_name(
        self,
        db: Session,
        normalised_name: str,
    ) -> Teacher | None:
        """Find an existing teacher by normalized full name."""
        teachers = db.query(Teacher).order_by(Teacher.ci).all()
        for teacher in teachers:
            if normalize_name(teacher.full_name) == normalised_name:
                return teacher
        return None

    def _merge_temp_teacher_into_existing(
        self,
        db: Session,
        temp_teacher: Teacher,
        real_teacher: Teacher,
    ) -> None:
        """Merge a TEMP teacher into an existing real teacher without violating designation uniqueness."""
        temp_designations = (
            db.query(Designation)
            .filter(Designation.teacher_ci == temp_teacher.ci)
            .all()
        )

        real_designations = {
            (designation.subject, designation.semester, designation.group_code): designation
            for designation in db.query(Designation)
            .filter(Designation.teacher_ci == real_teacher.ci)
            .all()
        }

        for temp_designation in temp_designations:
            key = (
                temp_designation.subject,
                temp_designation.semester,
                temp_designation.group_code,
            )
            real_designation = real_designations.get(key)

            if real_designation is not None:
                temp_attendance = aliased(AttendanceRecord)
                real_attendance = aliased(AttendanceRecord)

                colliding_temp_attendance_ids = [
                    row_id
                    for (row_id,) in db.execute(
                        select(temp_attendance.id)
                        .where(temp_attendance.designation_id == temp_designation.id)
                        .where(
                            exists(
                                select(1).where(
                                    and_(
                                        real_attendance.designation_id == real_designation.id,
                                        real_attendance.teacher_ci == real_teacher.ci,
                                        real_attendance.date == temp_attendance.date,
                                        real_attendance.scheduled_start == temp_attendance.scheduled_start,
                                    )
                                )
                            )
                        )
                    )
                ]

                if colliding_temp_attendance_ids:
                    db.query(AttendanceRecord).filter(
                        AttendanceRecord.id.in_(colliding_temp_attendance_ids)
                    ).delete(synchronize_session=False)

                db.query(AttendanceRecord).filter(
                    AttendanceRecord.designation_id == temp_designation.id
                ).update(
                    {
                        "teacher_ci": real_teacher.ci,
                        "designation_id": real_designation.id,
                    },
                    synchronize_session=False,
                )
                db.delete(temp_designation)
                continue

            db.query(Designation).filter(
                Designation.id == temp_designation.id
            ).update({"teacher_ci": real_teacher.ci}, synchronize_session=False)

        db.query(AttendanceRecord).filter(
            AttendanceRecord.teacher_ci == temp_teacher.ci
        ).update({"teacher_ci": real_teacher.ci}, synchronize_session=False)
        db.query(BiometricRecord).filter(
            BiometricRecord.teacher_ci == temp_teacher.ci
        ).update({"teacher_ci": real_teacher.ci}, synchronize_session=False)

        db.delete(temp_teacher)
