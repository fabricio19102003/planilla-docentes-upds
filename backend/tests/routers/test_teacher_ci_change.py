"""Changing a teacher CI must move every reference and keep portal login working.

Run against PostgreSQL too (TEST_DATABASE_URL), where foreign keys are
enforced and a naive child-first update fails.
"""
from datetime import date, time

from app.models.biometric import BiometricRecord, BiometricUpload
from app.models.designation import Designation
from app.models.practice_attendance import PracticeAttendanceLog
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service

PASSWORD = "Portal2026"


def _seed(db_session, *, user_ci="111"):
    teacher = Teacher(ci="111", full_name="Docente Mal Registrado", email="doc@upds.edu.bo", bank="BNB")
    db_session.add(teacher)
    db_session.flush()
    designation = Designation(
        teacher_ci="111",
        subject="Anatomía",
        semester="I",
        group_code="A",
        academic_period="II/2026",
        designation_type="regular",
        schedule_json=[],
        monthly_hours=10,
    )
    db_session.add(designation)
    db_session.flush()
    db_session.add(PracticeAttendanceLog(
        teacher_ci="111",
        designation_id=designation.id,
        date=date(2026, 10, 1),
        scheduled_start=time(8, 0),
        scheduled_end=time(10, 0),
    ))
    db_session.add(User(
        ci=user_ci,
        full_name="Docente Mal Registrado",
        password_hash=auth_service.hash_password(PASSWORD),
        role="docente",
        teacher_ci="111",
    ))
    # Commit (inside the fixture's outer transaction) so a route rollback
    # cannot discard the seed.
    db_session.commit()
    return designation.id


def _login(client, ci):
    return client.post("/api/auth/login", json={"ci": ci, "password": PASSWORD})


def test_ci_change_moves_references_and_portal_login(client, db_session):
    designation_id = _seed(db_session)

    response = client.put("/api/teachers/111", json={"ci": "222", "phone": "70000000"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ci"] == "222"
    assert body["phone"] == "70000000"
    assert body["email"] == "doc@upds.edu.bo"
    assert body["bank"] == "BNB"
    db_session.expire_all()
    assert db_session.get(Teacher, "111") is None
    assert db_session.get(Designation, designation_id).teacher_ci == "222"
    assert db_session.query(PracticeAttendanceLog).filter_by(teacher_ci="222").count() == 1
    assert db_session.query(PracticeAttendanceLog).filter_by(teacher_ci="111").count() == 0
    user = db_session.query(User).filter_by(teacher_ci="222").one()
    assert user.ci == "222"

    assert _login(client, "222").status_code == 200
    assert _login(client, "111").status_code == 401


def test_ci_change_syncs_portal_user_whose_login_differs_from_old_ci(client, db_session):
    _seed(db_session, user_ci="111-TEMP")

    response = client.put("/api/teachers/111", json={"ci": "222"})

    assert response.status_code == 200, response.text
    db_session.expire_all()
    user = db_session.query(User).filter_by(teacher_ci="222").one()
    assert user.ci == "222"
    assert _login(client, "222").status_code == 200


def test_ci_change_rejects_ci_owned_by_another_user_and_changes_nothing(client, db_session):
    designation_id = _seed(db_session)
    db_session.add(User(ci="222", full_name="Otra Persona", password_hash="x", role="admin"))
    db_session.commit()

    response = client.put("/api/teachers/111", json={"ci": "222"})

    assert response.status_code == 409
    assert response.json()["detail"] == "El CI 222 ya está en uso por el usuario Otra Persona"
    db_session.expire_all()
    assert db_session.get(Teacher, "111") is not None
    assert db_session.get(Teacher, "222") is None
    assert db_session.get(Designation, designation_id).teacher_ci == "111"
    assert db_session.query(User).filter_by(teacher_ci="111").one().ci == "111"


def test_ci_change_still_rejects_existing_teacher_ci(client, db_session):
    _seed(db_session)
    db_session.add(Teacher(ci="222", full_name="Otro Docente"))
    db_session.commit()

    response = client.put("/api/teachers/111", json={"ci": "222"})

    assert response.status_code == 409
    assert response.json()["detail"] == "Ya existe un docente con CI 222"
    db_session.expire_all()
    assert db_session.query(User).filter_by(teacher_ci="111").one().ci == "111"


def test_update_without_ci_change_still_updates_fields(client, db_session):
    _seed(db_session)

    response = client.put("/api/teachers/111", json={"phone": "71111111"})

    assert response.status_code == 200, response.text
    assert response.json()["ci"] == "111"
    assert response.json()["phone"] == "71111111"


def _assert_unchanged(db_session, designation_id):
    db_session.expire_all()
    assert db_session.get(Teacher, "111") is not None
    assert db_session.get(Teacher, "222") is None
    assert db_session.get(Designation, designation_id).teacher_ci == "111"
    assert [u.ci for u in db_session.query(User).filter_by(teacher_ci="111")] == ["111"]


def test_ci_change_rejects_when_portal_user_registered_practice_logs(client, db_session):
    designation_id = _seed(db_session)
    log = db_session.query(PracticeAttendanceLog).filter_by(teacher_ci="111").one()
    log.registered_by = "111"
    db_session.commit()

    response = client.put("/api/teachers/111", json={"ci": "222"})

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "No se puede cambiar el CI: el usuario 111 figura como quien registró "
        "asistencias de prácticas"
    )
    _assert_unchanged(db_session, designation_id)
    assert db_session.query(PracticeAttendanceLog).filter_by(registered_by="111").count() == 1


def test_ci_change_rejects_biometric_marks_that_would_collide(client, db_session):
    designation_id = _seed(db_session)
    upload = BiometricUpload(filename="oct.xlsx", month=10, year=2026)
    db_session.add(upload)
    db_session.flush()
    for ci in ("111", "222"):
        db_session.add(BiometricRecord(upload_id=upload.id, teacher_ci=ci, date=date(2026, 10, 1), entry_time=time(8, 0)))
    db_session.commit()

    response = client.put("/api/teachers/111", json={"ci": "222"})

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "No se puede cambiar el CI: el biométrico ya tiene 1 marca(s) con el CI 222 "
        "en la misma fecha y hora que las del CI 111"
    )
    _assert_unchanged(db_session, designation_id)
    assert db_session.query(BiometricRecord).filter_by(teacher_ci="111").count() == 1


def test_ci_change_moves_biometric_marks_without_collision(client, db_session):
    _seed(db_session)
    upload = BiometricUpload(filename="oct.xlsx", month=10, year=2026)
    db_session.add(upload)
    db_session.flush()
    db_session.add(BiometricRecord(upload_id=upload.id, teacher_ci="111", date=date(2026, 10, 1), entry_time=time(8, 0)))
    db_session.add(BiometricRecord(upload_id=upload.id, teacher_ci="222", date=date(2026, 10, 2), entry_time=time(8, 0)))
    db_session.commit()

    response = client.put("/api/teachers/111", json={"ci": "222"})

    assert response.status_code == 200, response.text
    db_session.expire_all()
    assert db_session.query(BiometricRecord).filter_by(teacher_ci="222").count() == 2


def test_ci_change_rejects_teacher_with_two_portal_users(client, db_session):
    designation_id = _seed(db_session)
    db_session.add(User(ci="111-B", full_name="Duplicado", password_hash="x", role="docente", teacher_ci="111"))
    db_session.commit()

    response = client.put("/api/teachers/111", json={"ci": "222"})

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "No se puede cambiar el CI: el docente tiene 2 usuarios del portal vinculados; "
        "dejá uno solo"
    )
    db_session.expire_all()
    assert db_session.get(Teacher, "111") is not None
    assert db_session.get(Designation, designation_id).teacher_ci == "111"
    assert sorted(u.ci for u in db_session.query(User).filter_by(teacher_ci="111")) == ["111", "111-B"]
