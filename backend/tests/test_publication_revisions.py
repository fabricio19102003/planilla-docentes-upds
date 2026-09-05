from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import settings
from app.models.billing_publication import BillingPublication, BillingPublicationRevision
from app.services.publication_revisions import PublicationRevisionError
from tests.routers.test_billing_publication_email import (
    _calculation_snapshot,
    _fake_planilla_rows,
    _fake_practice_planilla_rows,
    _seed_approved_planilla,
    _seed_approved_practice_planilla,
)


CASES = [
    ("/api/billing/publish", "/api/billing/unpublish", _seed_approved_planilla, _fake_planilla_rows, "regular", Decimal("600")),
    ("/api/billing/practice/publish", "/api/billing/practice/unpublish", _seed_approved_practice_planilla, _fake_practice_planilla_rows, "practice", Decimal("450")),
]


@pytest.mark.parametrize(("publish_url", "unpublish_url", "seed", "row_factory", "kind", "v2_total"), CASES)
def test_publication_revisions_are_append_only_and_unpublish_preserves_them(
    client, db_session, monkeypatch, publish_url, unpublish_url, seed, row_factory, kind, v2_total
):
    output = seed(db_session)
    monkeypatch.setattr(
        "app.routers.billing_publication.EmailService.send_billing_published",
        lambda *args: SimpleNamespace(eligible=0, sent=0, failed=0, skipped=0),
    )
    payload = {"month": 5, "year": 2026}

    assert client.post(publish_url, json=payload).status_code == 200
    publication = db_session.query(BillingPublication).filter_by(planilla_type=kind).one()
    first = db_session.query(BillingPublicationRevision).filter_by(publication_id=publication.id).one()
    original = deepcopy(first.billing_snapshot)

    rows = row_factory(None, None, 5, 2026)[0]
    output.total_payment = v2_total
    output.calculation_snapshot = _calculation_snapshot(rows, v2_total)
    db_session.commit()

    assert client.post(publish_url, json=payload).status_code == 200
    revisions = db_session.query(BillingPublicationRevision).filter_by(publication_id=publication.id).order_by(BillingPublicationRevision.version).all()
    assert [revision.version for revision in revisions] == [1, 2]
    assert revisions[0].billing_snapshot == original
    assert revisions[0].calculation_digest != revisions[1].calculation_digest
    assert publication.version == 2

    assert client.post(unpublish_url, json=payload).status_code == 200
    db_session.refresh(publication)
    assert publication.status == "draft"
    assert db_session.query(BillingPublicationRevision).filter_by(publication_id=publication.id).count() == 2
    assert revisions[0].billing_snapshot == original
    duplicate = client.post(publish_url, json=payload)
    assert (duplicate.status_code, duplicate.json()["detail"]["code"]) == (409, "snapshot_already_published")


def test_legacy_publication_without_revision_requires_manual_backfill(client, db_session):
    _seed_approved_planilla(db_session)
    db_session.add(BillingPublication(
        month=5, year=2026, planilla_type="regular", status="published", version=1,
        total_teachers=1, total_payment=560, billing_snapshot={"legacy": True},
    ))
    db_session.commit()

    response = client.post("/api/billing/publish", json={"month": 5, "year": 2026})

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "legacy_revision_missing"


def test_publication_revision_error_has_stable_detail():
    assert PublicationRevisionError("code", "message").as_detail() == {"code": "code", "message": "message"}


def test_revision_migration_upgrades_and_downgrades_sqlite(tmp_path, monkeypatch):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / 'revisions.sqlite3'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE billing_publications (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version VALUES ('e5f2a7c9d301')"))
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)

    command.upgrade(config, "f7a1b2c3d4e5")
    assert inspect(engine).has_table("billing_publication_revisions")
    names = {item["name"] for item in inspect(engine).get_unique_constraints("billing_publication_revisions")}
    assert names == {"uq_billing_revision_version", "uq_billing_revision_calculation_digest"}
    command.downgrade(config, "e5f2a7c9d301")
    assert not inspect(engine).has_table("billing_publication_revisions")
    engine.dispose()
