from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from app.models.attendance import AttendanceRecord
from app.models.biometric import BiometricRecord, BiometricUpload
from app.models.designation import Designation
from app.models.planilla import PlanillaOutput
from app.models.teacher import Teacher
from app.services.attendance_engine import ProcessResult
from app.services.planilla_generator import PlanillaResult


def seed_core_data(db_session):
    teacher = Teacher(ci="123456", full_name="Ana Perez", email="ana@example.com")
    db_session.add(teacher)
    db_session.flush()

    designation = Designation(
        teacher_ci=teacher.ci,
        subject="Anatomia",
        semester="1",
        group_code="M-1",
        schedule_json=[
            {
                "dia": "lunes",
                "hora_inicio": "08:00",
                "hora_fin": "09:30",
                "horas_academicas": 2,
            }
        ],
        weekly_hours=2,
        monthly_hours=8,  # Model C: base pay = 8 × 70 = 560 Bs
    )
    db_session.add(designation)

    upload = BiometricUpload(
        filename="20260301_biometrico.xls",
        month=3,
        year=2026,
        total_records=1,
        total_teachers=1,
        status="completed",
    )
    db_session.add(upload)
    db_session.flush()

    biometric_record = BiometricRecord(
        upload_id=upload.id,
        teacher_ci=teacher.ci,
        teacher_name=teacher.full_name,
        date=date(2026, 3, 2),
        entry_time=time(8, 7),
        exit_time=time(9, 32),
        worked_minutes=85,
    )
    db_session.add(biometric_record)
    db_session.flush()

    attendance = AttendanceRecord(
        teacher_ci=teacher.ci,
        designation_id=designation.id,
        date=date(2026, 3, 2),
        scheduled_start=time(8, 0),
        scheduled_end=time(9, 30),
        actual_entry=time(8, 7),
        actual_exit=time(9, 32),
        status="LATE",
        academic_hours=2,
        late_minutes=7,
        observation="Llegada tardía: 7 min después de 08:00",
        biometric_record_id=biometric_record.id,
        month=3,
        year=2026,
    )
    db_session.add(attendance)

    output = PlanillaOutput(
        month=3,
        year=2026,
        generated_at=datetime(2026, 3, 31, 12, 0, 0),
        file_path=str(Path("backend/data/output/test_planilla.xlsx").resolve()),
        total_teachers=1,
        total_hours=2,
        total_payment=Decimal("140.00"),
        status="generated",
    )
    db_session.add(output)
    db_session.commit()

    return {
        "teacher": teacher,
        "designation": designation,
        "upload": upload,
        "biometric_record": biometric_record,
        "attendance": attendance,
        "output": output,
    }


def test_health_and_docs(client):
    assert client.get("/health").status_code == 200
    assert client.get("/docs").status_code == 200


def test_upload_history_and_designation_upload(client, db_session, tmp_path):
    seed_core_data(db_session)

    history_response = client.get("/api/uploads/history")
    assert history_response.status_code == 200
    assert history_response.json()[0]["filename"] == "20260301_biometrico.xls"

    designation_file = tmp_path / "designaciones.json"
    designation_file.write_text(
        """
        {
          "designaciones": [
            {
              "docente": "Ana Perez",
              "materia": "Fisiologia",
              "semestre": "2",
              "grupo": "T-1",
              "carga_horaria_semestral": 32,
              "carga_horaria_mensual": 8,
              "carga_horaria_semanal": 2,
              "total_horas_academicas_semanal_calculado": 2,
              "horario_raw": "Martes 10:00-11:30",
              "horario": [
                {
                  "dia": "martes",
                  "hora_inicio": "10:00",
                  "hora_fin": "11:30",
                  "duracion_minutos": 90,
                  "horas_academicas": 2
                }
              ]
            }
          ]
        }
        """.strip(),
        encoding="utf-8",
    )

    with designation_file.open("rb") as handle:
        response = client.post(
            "/api/uploads/designations",
            files={"file": (designation_file.name, handle, "application/json")},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["designations_loaded"] >= 1


def test_biometric_upload_smoke(client, db_session, monkeypatch, tmp_path):
    import app.routers.biometric as biometric_router_module
    from app.services.biometric_parser import BiometricEntry, BiometricParseResult

    def fake_parse_file(self, file_path):
        return BiometricParseResult(
            metadata={},
            records={
                "123456": [
                    BiometricEntry(
                        teacher_name="Ana Perez",
                        ci="123456",
                        date=date(2026, 3, 2),
                        entry_time=time(8, 0),
                        exit_time=time(9, 30),
                        worked_minutes=90,
                        shift="M",
                    )
                ]
            },
            stats={"total_teachers": 1, "total_records": 1},
            warnings=[],
        )

    def fake_link_teachers_by_name(self, db, ci_name_map):
        return 0

    monkeypatch.setattr(biometric_router_module.BiometricParser, "parse_file", fake_parse_file)
    monkeypatch.setattr(biometric_router_module.DesignationLoader, "link_teachers_by_name", fake_link_teachers_by_name)

    biometric_file = tmp_path / "bio.xls"
    biometric_file.write_bytes(b"fake xls content")

    with biometric_file.open("rb") as handle:
        response = client.post(
            "/api/uploads/biometric",
            data={"month": 3, "year": 2026},
            files={"file": (biometric_file.name, handle, "application/vnd.ms-excel")},
        )

    assert response.status_code == 201
    payload = response.json()
    assert payload["teachers_found"] == 1
    assert payload["records_count"] == 1


def test_attendance_endpoints(client, db_session, monkeypatch):
    seeded = seed_core_data(db_session)

    import app.routers.attendance as attendance_router_module

    def fake_process_month(self, db, upload_id, month, year, start_date=None, end_date=None):
        return ProcessResult(
            upload_id=upload_id,
            month=month,
            year=year,
            total_slots=1,
            attended=0,
            late=1,
            absent=0,
            no_exit=0,
        )

    monkeypatch.setattr(attendance_router_module.AttendanceEngine, "process_month", fake_process_month)

    process_response = client.post(
        "/api/attendance/process",
        json={"upload_id": seeded["upload"].id, "month": 3, "year": 2026},
    )
    assert process_response.status_code == 200
    assert process_response.json()["total_records"] == 1

    list_response = client.get("/api/attendance/3/2026")
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["teacher_name"] == "Ana Perez"

    summary_response = client.get("/api/attendance/3/2026/summary")
    assert summary_response.status_code == 200
    assert summary_response.json()["late"] >= 1

    observations_response = client.get("/api/observations/3/2026?type=LATE")
    assert observations_response.status_code == 200
    assert observations_response.json()[0]["status"] == "LATE"


def test_teacher_planilla_and_dashboard_endpoints(client, db_session, monkeypatch, tmp_path):
    seeded = seed_core_data(db_session)

    output_file = tmp_path / "planilla_generada.xlsx"
    output_file.write_bytes(b"xlsx-content")
    seeded["output"].file_path = str(output_file)
    db_session.commit()

    teachers_response = client.get("/api/teachers")
    assert teachers_response.status_code == 200
    assert teachers_response.json()["items"][0]["ci"] == "123456"

    teacher_response = client.get("/api/teachers/123456")
    assert teacher_response.status_code == 200
    assert teacher_response.json()["attendance_summary"]["late"] == 1

    history_response = client.get("/api/planilla/history")
    assert history_response.status_code == 200
    assert history_response.json()[0]["total_payment"] == "140.00"

    import app.routers.planilla as planilla_router_module

    def fake_generate(self, db, month, year, payment_overrides=None, start_date=None, end_date=None):
        output = PlanillaOutput(
            month=month,
            year=year,
            file_path=str(output_file),
            total_teachers=1,
            total_hours=2,
            total_payment=Decimal("150.00"),
            status="generated",
        )
        db.add(output)
        db.flush()
        return PlanillaResult(
            file_path=str(output_file),
            month=month,
            year=year,
            total_teachers=1,
            total_rows=1,
            total_hours=2,
            total_payment=150.0,
            planilla_output_id=output.id,
            warnings=[],
        )

    monkeypatch.setattr(planilla_router_module.PlanillaGenerator, "generate", fake_generate)

    generate_response = client.post("/api/planilla/generate", json={"month": 4, "year": 2026})
    assert generate_response.status_code == 200
    assert generate_response.json()["planilla_id"] > 0

    download_response = client.get(f"/api/planilla/{seeded['output'].id}/download")
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    dashboard_response = client.get("/api/dashboard/summary")
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["teacher_count"] >= 1
