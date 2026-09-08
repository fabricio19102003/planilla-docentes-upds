from __future__ import annotations

from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.routers import teachers as teachers_router
from app.services.auth_service import auth_service


def test_admin_downloads_teacher_active_schedule_as_pdf(client, db_session):
    teacher = Teacher(ci="SCHEDULE-1", full_name="Schedule Teacher")
    designation = Designation(
        teacher_ci=teacher.ci,
        subject="Anatomy",
        semester="I",
        group_code="M1",
        academic_period="I/2026",
        schedule_json=[{
            "dia": "Lunes",
            "hora_inicio": "08:00",
            "hora_fin": "09:30",
            "horas_academicas": 2,
        }],
        weekly_hours=2,
    )
    db_session.add_all([teacher, designation])
    db_session.commit()

    response = client.get("/api/teachers/SCHEDULE-1/schedule/pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-type"].startswith("application/pdf")
    assert "attachment" in response.headers["content-disposition"]


def test_admin_schedule_download_returns_404_for_unknown_teacher(client):
    response = client.get("/api/teachers/UNKNOWN/schedule/pdf")

    assert response.status_code == 404


def test_admin_schedule_download_scopes_designations_to_active_period(client, db_session, monkeypatch):
    teacher = Teacher(ci="SCHEDULE-PERIOD", full_name="Period Schedule")
    active = Designation(
        teacher_ci=teacher.ci,
        subject="Active Subject",
        semester="I",
        group_code="M1",
        academic_period="I/2026",
        schedule_json=[],
    )
    inactive = Designation(
        teacher_ci=teacher.ci,
        subject="Inactive Subject",
        semester="I",
        group_code="M2",
        academic_period="II/2025",
        schedule_json=[],
    )
    db_session.add_all([teacher, active, inactive])
    db_session.commit()
    captured: list[str] = []

    def fake_pdf(_teacher, designations):
        captured.extend(designation.subject for designation in designations)
        return b"%PDF-active-period"

    monkeypatch.setattr(teachers_router, "generate_schedule_pdf", fake_pdf)

    response = client.get("/api/teachers/SCHEDULE-PERIOD/schedule/pdf")

    assert response.status_code == 200
    assert captured == ["Active Subject"]


def test_teacher_cannot_download_an_admin_teacher_schedule(client, db_session):
    teacher = Teacher(ci="SCHEDULE-PRIVATE", full_name="Private Schedule")
    user = User(
        ci="SCHEDULE-PRIVATE",
        full_name="Private Schedule",
        password_hash="unused",
        role="docente",
        teacher_ci=teacher.ci,
        is_active=True,
    )
    db_session.add_all([teacher, user])
    db_session.commit()
    token = auth_service.create_access_token({"sub": str(user.id), "role": "docente"})

    response = client.get(
        "/api/teachers/SCHEDULE-PRIVATE/schedule/pdf",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
