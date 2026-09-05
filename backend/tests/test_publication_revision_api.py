from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.billing_publication import BillingPublication, BillingPublicationRevision
from app.models.user import User
from app.services.auth_service import auth_service
from tests.routers.test_billing_publication_email import (
    _calculation_snapshot,
    _fake_planilla_rows,
    _fake_practice_planilla_rows,
    _seed_approved_planilla,
    _seed_approved_practice_planilla,
)


CASES = [
    ("regular", "/api/billing/publish", _seed_approved_planilla, _fake_planilla_rows, Decimal("600")),
    ("practice", "/api/billing/practice/publish", _seed_approved_practice_planilla, _fake_practice_planilla_rows, Decimal("450")),
]


def _publish_two(client, db, monkeypatch, kind, publish_url, seed, row_factory, total):
    output = seed(db)
    monkeypatch.setattr(
        "app.routers.billing_publication.EmailService.send_billing_published",
        lambda *args: SimpleNamespace(eligible=0, sent=0, failed=0, skipped=0),
    )
    payload = {"month": 5, "year": 2026}
    assert client.post(publish_url, json=payload).status_code == 200
    output.total_payment = total
    output.calculation_snapshot = _calculation_snapshot(row_factory(None, None, 5, 2026)[0], total)
    db.commit()
    assert client.post(publish_url, json=payload).status_code == 200


@pytest.mark.parametrize(("kind", "publish_url", "seed", "row_factory", "total"), CASES)
def test_revision_api_lists_details_and_identifies_current(
    client, db_session, monkeypatch, kind, publish_url, seed, row_factory, total
):
    _publish_two(client, db_session, monkeypatch, kind, publish_url, seed, row_factory, total)
    base = f"/api/billing/revisions/{kind}/5/2026"

    listed = client.get(base)
    assert listed.status_code == 200
    assert [item["version"] for item in listed.json()] == [1, 2]
    assert listed.json()[1]["total_payment"] == float(total)
    assert "teacher_details" not in listed.text and "teacher_ci" not in listed.text

    current = client.get(f"{base}/current")
    assert current.status_code == 200
    assert current.json()["revision_count"] == 2
    assert current.json()["current_revision"]["version"] == 2

    detail = client.get(f"{base}/1")
    assert detail.status_code == 200
    assert detail.json()["version"] == 1
    assert detail.json()["calculation_snapshot"]["digest"] == detail.json()["calculation_digest"]
    assert detail.json()["billing_snapshot"]["calculation_snapshot_digest"] == detail.json()["calculation_digest"]


def test_revision_api_requires_admin(client, db_session):
    client.headers.pop("Authorization")
    response = client.get("/api/billing/revisions/regular/5/2026")
    assert response.status_code == 401
    docente = User(
        ci="REVISION_DOCENTE", full_name="Revision Docente",
        password_hash=auth_service.hash_password("testpass123"), role="docente", is_active=True,
    )
    db_session.add(docente)
    db_session.commit()
    token = auth_service.create_access_token(data={"sub": str(docente.id), "role": "docente"})
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/api/billing/revisions/regular/5/2026").status_code == 403


def test_revision_api_returns_not_found(client, db_session):
    assert client.get("/api/billing/revisions/regular/5/2026").status_code == 404
    publication = BillingPublication(
        month=5, year=2026, planilla_type="regular", status="published", version=1,
        total_teachers=0, total_payment=0,
    )
    db_session.add(publication)
    db_session.flush()
    db_session.add(BillingPublicationRevision(
        publication_id=publication.id, version=1, status="published",
        calculation_digest="a" * 64, billing_digest="b" * 64,
        calculation_snapshot={}, billing_snapshot={},
    ))
    db_session.commit()
    assert client.get("/api/billing/revisions/regular/5/2026/2").status_code == 404


@pytest.mark.parametrize(("corrupt_field", "corrupt_value"), [
    ("billing_digest", "0" * 64), ("calculation_digest", "0" * 64),
])
def test_revision_api_rejects_legacy_and_corruption(
    client, db_session, monkeypatch, corrupt_field, corrupt_value
):
    legacy = BillingPublication(
        month=4, year=2026, planilla_type="regular", status="published", version=1,
        total_teachers=1, total_payment=10, billing_snapshot={"legacy": True},
    )
    db_session.add(legacy)
    db_session.commit()
    response = client.get("/api/billing/revisions/regular/4/2026")
    assert (response.status_code, response.json()["detail"]["code"]) == (409, "legacy_revision_missing")

    _publish_two(client, db_session, monkeypatch, *CASES[0])
    revision = db_session.query(BillingPublicationRevision).filter_by(version=1).one()
    setattr(revision, corrupt_field, corrupt_value)
    db_session.commit()
    response = client.get("/api/billing/revisions/regular/5/2026/1")
    assert (response.status_code, response.json()["detail"]["code"]) == (409, "revision_corrupt")
