from __future__ import annotations

from datetime import date, time

from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricRecord, BiometricUpload
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service


def _docente_authorization(db_session, teacher: Teacher) -> str:
    user = User(
        ci=f"REQUEST-{teacher.ci}",
        full_name=teacher.full_name,
        password_hash=auth_service.hash_password("Testpass123"),
        role="docente",
        teacher_ci=teacher.ci,
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    token = auth_service.create_access_token(data={"sub": str(user.id), "role": "docente"})
    return f"Bearer {token}"


def test_admin_response_persists_typed_historical_resolution_snapshots(
    client,
    db_session,
):
    teacher = Teacher(ci="REQUEST-SNAPSHOT-1", full_name="Snapshot Teacher")
    db_session.add(teacher)
    db_session.flush()

    designation = Designation(
        teacher_ci=teacher.ci,
        subject="Anatomy I",
        semester="First semester",
        group_code="M1",
        academic_period="I/2026",
        schedule_json=[
            {
                "dia": "Lunes",
                "hora_inicio": "08:00",
                "hora_fin": "09:30",
                "horas_academicas": 2,
            }
        ],
        weekly_hours=2,
        monthly_hours=8,
    )
    db_session.add(designation)
    db_session.flush()

    attendance = AttendanceRecord(
        teacher_ci=teacher.ci,
        designation_id=designation.id,
        date=date(2026, 4, 6),
        scheduled_start=time(8, 0),
        scheduled_end=time(9, 30),
        actual_entry=time(7, 58),
        actual_exit=time(9, 32),
        status="ATTENDED",
        academic_hours=2,
        late_minutes=0,
        month=4,
        year=2026,
    )
    upload = BiometricUpload(
        filename="april.xls",
        month=4,
        year=2026,
        total_records=1,
        total_teachers=1,
        status="completed",
    )
    db_session.add_all([attendance, upload])
    db_session.flush()
    biometric = BiometricRecord(
        upload_id=upload.id,
        teacher_ci=teacher.ci,
        teacher_name=teacher.full_name,
        date=date(2026, 4, 6),
        entry_time=time(7, 58),
        exit_time=time(9, 32),
        worked_minutes=94,
        shift="Mañana",
    )
    db_session.add(biometric)
    db_session.commit()

    admin_authorization = client.headers["Authorization"]
    docente_authorization = _docente_authorization(db_session, teacher)
    db_session.commit()

    client.headers["Authorization"] = docente_authorization
    request_ids: dict[str, int] = {}
    for request_type in ("schedule_detail", "hours_summary", "biometric_detail"):
        created = client.post(
            "/api/detail-requests",
            json={"month": 4, "year": 2026, "request_type": request_type},
        )
        assert created.status_code == 201
        request_ids[request_type] = created.json()["id"]

    client.headers["Authorization"] = admin_authorization
    for request_type, request_id in request_ids.items():
        responded = client.put(
            f"/api/detail-requests/{request_id}/respond",
            json={"status": "approved", "admin_response": f"Observation for {request_type}"},
        )
        assert responded.status_code == 200
        assert responded.json()["resolution_snapshot"]["kind"] == request_type

    designation.schedule_json = []
    biometric.entry_time = time(10, 0)
    attendance.academic_hours = 9
    db_session.commit()

    client.headers["Authorization"] = docente_authorization
    mine = client.get("/api/detail-requests/my")
    assert mine.status_code == 200
    by_type = {item["request_type"]: item for item in mine.json()}

    schedule = by_type["schedule_detail"]
    assert schedule["admin_response"] == "Observation for schedule_detail"
    assert schedule["resolution_snapshot"] == {
        "kind": "schedule_detail",
        "academic_period": "I/2026",
        "designations": [
            {
                "subject": "Anatomy I",
                "semester": "First semester",
                "group_code": "M1",
                "weekly_hours": 2,
                "monthly_hours": 8,
                "schedule": [
                    {
                        "dia": "Lunes",
                        "hora_inicio": "08:00",
                        "hora_fin": "09:30",
                        "horas_academicas": 2,
                    }
                ],
            }
        ],
    }

    hours = by_type["hours_summary"]["resolution_snapshot"]
    assert hours == {
        "kind": "hours_summary",
        "month": 4,
        "year": 2026,
        "total_records": 1,
        "total_academic_hours": 2,
        "status_counts": {"ATTENDED": 1},
    }

    biometric_snapshot = by_type["biometric_detail"]["resolution_snapshot"]
    assert biometric_snapshot == {
        "kind": "biometric_detail",
        "month": 4,
        "year": 2026,
        "records": [
            {
                "date": "2026-04-06",
                "entry_time": "07:58:00",
                "exit_time": "09:32:00",
                "worked_minutes": 94,
                "shift": "Mañana",
            }
        ],
    }
