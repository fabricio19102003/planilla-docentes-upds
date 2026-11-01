"""Files the backend reads at runtime must survive the image's .dockerignore."""
from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from app.services import academic_records_service

REPO = Path(__file__).resolve().parents[2]


def _ignored(path: str) -> bool:
    """Docker semantics: the last matching pattern wins; a parent excluded by `dir/*` hides its children."""
    ignored = False
    for line in (REPO / ".dockerignore").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        negated, pattern = line.startswith("!"), line.lstrip("!")
        if fnmatch(path, pattern) or fnmatch(path, pattern.replace("/**", "")):
            ignored = not negated
    return ignored


def test_the_bundled_curriculum_is_part_of_the_backend_image():
    curriculum = academic_records_service.DEFAULT_CURRICULUM_PATH.resolve().relative_to(REPO).as_posix()

    assert curriculum == "backend/data/curricula/medicina-510-01.json"
    assert not _ignored(curriculum)


def test_operational_data_stays_out_of_the_image():
    assert _ignored("backend/data/gestion-2026.csv")
    assert not _ignored("backend/data/assets/logo.png")
