from __future__ import annotations

from types import SimpleNamespace

from app.services.schedule_pdf import collect_schedule_grid, generate_schedule_pdf, schedule_download_filename


def _designation(subject: str, group: str):
    return SimpleNamespace(
        subject=subject,
        group_code=group,
        semester="I",
        weekly_hours=2,
        schedule_json=[{
            "dia": "Lunes",
            "hora_inicio": "08:00",
            "hora_fin": "09:30",
            "horas_academicas": 2,
        }],
    )


def test_schedule_grid_preserves_simultaneous_classes():
    grid = collect_schedule_grid([
        _designation("Anatomy", "M1"),
        _designation("Physiology", "M2"),
    ])

    cell = grid.slots_by_cell[("08:00", "Lunes")]
    assert [(slot["subject"], slot["group_code"]) for slot in cell] == [
        ("Anatomy", "M1"),
        ("Physiology", "M2"),
    ]


def test_generate_schedule_pdf_returns_bytes_without_writing_pii_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    teacher = SimpleNamespace(ci="../unsafe-ci", full_name="Teacher Name")

    pdf = generate_schedule_pdf(teacher, [_designation("Anatomy", "M1")])

    assert pdf.startswith(b"%PDF")
    assert list(tmp_path.rglob("*.pdf")) == []


def test_schedule_download_filename_is_safe_and_ascii():
    filename = schedule_download_filename("../../José / Docente")

    assert filename.startswith("Horario_de_Jose_Docente_Gestion_")
    assert filename.endswith(".pdf")
    assert "/" not in filename
    filename.encode("ascii")
