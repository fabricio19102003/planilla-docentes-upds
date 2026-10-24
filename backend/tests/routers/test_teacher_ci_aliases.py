"""Months published under a teacher's previous CI stay visible in the portal."""
from datetime import datetime, timedelta
from decimal import Decimal

from app.models.billing_publication import BillingPublication
from app.models.teacher import Teacher
from app.models.user import User
from app.services.auth_service import auth_service


def _seed_docente(db_session, ci="111"):
    teacher = Teacher(ci=ci, full_name="Docente Corregido")
    db_session.add(teacher)
    db_session.flush()
    user = User(
        ci=ci,
        full_name=teacher.full_name,
        password_hash=auth_service.hash_password("Portal2026"),
        role="docente",
        teacher_ci=ci,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _publish(db_session, *, month, snapshot_ci, published_at, payment=609):
    db_session.add(BillingPublication(
        month=month,
        year=2026,
        planilla_type="regular",
        status="published",
        version=1,
        total_teachers=1,
        total_payment=Decimal(payment),
        published_at=published_at,
        billing_snapshot={
            "rate_per_hour": 70,
            "teacher_details": [{
                "teacher_ci": snapshot_ci,
                "has_retention": False,
                "total_hours": 10,
                "gross_payment": payment,
                "retention_amount": 0,
                "final_payment": payment,
                "total_payment": payment,
                "designations": [{
                    "subject": "Anatomía", "semester": "I", "group": "A",
                    "payable_hours": 10, "gross_payment": payment,
                    "retention_amount": 0, "payment": payment,
                }],
            }],
        },
    ))
    db_session.commit()


def _history_as(client, user):
    admin_auth = client.headers["Authorization"]
    token = auth_service.create_access_token(data={"sub": str(user.id), "role": "docente"})
    client.headers["Authorization"] = f"Bearer {token}"
    try:
        response = client.get("/api/portal/billing/history")
    finally:
        client.headers["Authorization"] = admin_auth
    assert response.status_code == 200, response.text
    return [(item["month"], item["net_payment"]) for item in response.json()]


def test_history_keeps_months_published_under_the_previous_ci(client, db_session):
    user = _seed_docente(db_session)
    _publish(db_session, month=4, snapshot_ci="111", published_at=datetime(2026, 4, 30, 12))

    assert client.put("/api/teachers/111", json={"ci": "222"}).status_code == 200

    assert _history_as(client, user) == [(4, 609.0)]


def test_history_follows_chained_ci_corrections(client, db_session):
    user = _seed_docente(db_session)
    _publish(db_session, month=4, snapshot_ci="111", published_at=datetime(2026, 4, 30, 12))
    assert client.put("/api/teachers/111", json={"ci": "222"}).status_code == 200
    _publish(db_session, month=5, snapshot_ci="222", published_at=datetime(2026, 5, 31, 12), payment=700)

    assert client.put("/api/teachers/222", json={"ci": "333"}).status_code == 200

    assert _history_as(client, user) == [(5, 700.0), (4, 609.0)]


def test_previous_ci_reused_by_another_teacher_does_not_leak_new_months(client, db_session):
    user = _seed_docente(db_session)
    _publish(db_session, month=4, snapshot_ci="111", published_at=datetime(2026, 4, 30, 12))
    assert client.put("/api/teachers/111", json={"ci": "222"}).status_code == 200
    # The real owner of CI 111 is registered later and gets paid under it.
    db_session.add(Teacher(ci="111", full_name="Titular Real del CI"))
    db_session.commit()
    _publish(db_session, month=5, snapshot_ci="111", published_at=datetime.utcnow() + timedelta(days=1), payment=999)

    assert _history_as(client, user) == [(4, 609.0)]


def test_failed_ci_change_records_no_alias(client, db_session):
    user = _seed_docente(db_session)
    _publish(db_session, month=4, snapshot_ci="111", published_at=datetime(2026, 4, 30, 12))
    db_session.add(Teacher(ci="222", full_name="Otro"))
    db_session.commit()

    assert client.put("/api/teachers/111", json={"ci": "222"}).status_code == 409

    # The other teacher must not inherit 111's months through a stray alias.
    other = User(ci="222", full_name="Otro", password_hash="x", role="docente", teacher_ci="222")
    db_session.add(other)
    db_session.commit()
    assert _history_as(client, other) == []
    assert _history_as(client, user) == [(4, 609.0)]
