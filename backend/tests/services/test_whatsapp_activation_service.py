import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.config import settings
from app.models.billing_notification import BillingNotificationJob, BillingWhatsAppActivationTest
from app.schemas.whatsapp_activation import WhatsAppActivationCreate, WhatsAppActivationProjection
from app.models.billing_notification import BillingMediaToken, BillingNotificationBatch, BillingWhatsAppActivationTest
from app.models.billing_publication import BillingPublicationRevision
from app.models.user import User
from app.models.whatsapp_preference import WhatsAppPreference
from app.services.billing_pdf_service import BillingPdfService
from app.services.whatsapp_activation_service import WhatsAppActivationError, WhatsAppActivationService
from tests.routers.test_billing_publication_email import _seed_approved_planilla, _seed_docente


def _activation_setup(client, db_session, tmp_path, monkeypatch):
    import app.routers.billing_publication as publication_router

    _seed_approved_planilla(db_session)
    _seed_docente(db_session, ci="EMAIL-DOC-1", email="activation@example.com")
    monkeypatch.setattr(publication_router.EmailService, "send_billing_published", lambda *_: type("R", (), {"eligible": 0, "sent": 0, "failed": 0, "skipped": 0})())
    assert client.post("/api/billing/publish", json={"month": 5, "year": 2026}).status_code == 200
    preference = WhatsAppPreference(teacher_ci="EMAIL-DOC-1", phone_e164="+59170000000", is_verified=True, consent_evidence="record", consent_source="written_record", consented_at=__import__("datetime").datetime.utcnow(), consent_revision=1)
    db_session.add(preference); db_session.flush()
    revision = db_session.query(BillingPublicationRevision).one()
    actor = db_session.query(User).filter_by(ci="TEST_ADMIN_9999").one()
    request = WhatsAppActivationCreate(teacher_ci="EMAIL-DOC-1", recipient_e164="+59170000000", consent_revision=1, publication_revision_id=revision.id)
    return WhatsAppActivationService(db_session, recipient_hmac_key="k" * 32, pdf_service=BillingPdfService(db_session, storage_dir=tmp_path)), actor, request, revision


def _ready(sid):
    return {"activation": {"capable": True}, "global_delivery": {"requested": False, "effective": False}, "provider_configuration": {"ready": True}, "provider_live": {"ready": True}, "approved_content_sid": sid}


def test_activation_create_schema_requires_exact_canonical_recipient():
    request = WhatsAppActivationCreate(
        teacher_ci="teacher-1", recipient_e164="+59170000000",
        consent_revision=1, publication_revision_id=1,
    )
    assert request.recipient_e164 == "+59170000000"
    with pytest.raises(ValueError, match="canonical E.164"):
        WhatsAppActivationCreate(teacher_ci="teacher-1", recipient_e164=" +59170000000", consent_revision=1, publication_revision_id=1)


def test_activation_requires_exact_attestation_and_strict_projection():
    sid = "HX" + "a" * 32
    WhatsAppActivationService._require_readiness(_ready(sid), sid, sid)
    with pytest.raises(WhatsAppActivationError, match="activation_template_unapproved"):
        WhatsAppActivationService._require_readiness(_ready(sid), sid, "HX" + "b" * 32)
    global_on = _ready(sid); global_on["global_delivery"]["effective"] = True
    with pytest.raises(WhatsAppActivationError, match="activation_requires_global_delivery_disabled"):
        WhatsAppActivationService._require_readiness(global_on, sid, sid)
    with pytest.raises(ValueError):
        WhatsAppActivationProjection(id=1, status="queued", terminal_reason=None, teacher_ci_at_creation="T", recipient_masked="+591••••0000", consent_revision=1, publication_revision_id=1, publication_version=1, billing_digest="a" * 64, content_template_bound=True, pdf_bound=True, job_id=1, job_status="unknown", created_at=__import__("datetime").datetime.utcnow(), updated_at=__import__("datetime").datetime.utcnow())


def test_pdf_flush_cleanup_preserves_existing_artifact(tmp_path):
    db = type("DB", (), {"add": lambda *_: None, "flush": lambda *_: (_ for _ in ()).throw(RuntimeError("flush"))})()
    pdf = BillingPdfService(db, storage_dir=tmp_path); batch = type("B", (), {"id": 1})(); job = type("J", (), {"id": 1, "batch_id": 1, "teacher_ci": "T", "media_snapshot": None})()
    with pytest.raises(RuntimeError, match="flush"): pdf.issue(batch, job, {"x": 1}, commit=False)
    payload = pdf._pdf_bytes(1, "T", {"x": 1}); path = pdf._safe_path(f"b-{__import__('hashlib').sha256(payload).hexdigest()[:12]}.pdf"); path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(payload)
    with pytest.raises(RuntimeError, match="flush"): pdf.issue(batch, job, {"x": 1}, commit=False)
    assert path.exists()


def test_activation_failure_leaves_caller_transaction_ownership(client, db_session, tmp_path, monkeypatch):
    service, actor, request, _ = _activation_setup(client, db_session, tmp_path, monkeypatch); calls = []
    monkeypatch.setattr(db_session, "rollback", lambda: calls.append(True))
    monkeypatch.setattr(service.pdf_service, "issue_activation", lambda *_a, **_k: (_ for _ in ()).throw(OSError("storage")))
    with pytest.raises(OSError): service.create(actor_user_id=actor.id, request=request, idempotency_key="a" * 16, readiness=_ready("HX" + "a" * 32), configured_content_sid="HX" + "a" * 32, approved_content_sid="HX" + "a" * 32)
    assert not calls


ACTIVATION_MIGRATION = "a2c4e6f8b002"
PREVIOUS_MIGRATION = "a2c4e6f8b001"


def _config(tmp_path, monkeypatch, name):
    backend = Path(__file__).parents[2]
    url = f"sqlite:///{tmp_path / name}"
    engine = sa.create_engine(url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return engine, config


def _migration_module():
    path = Path(__file__).parents[2] / "alembic/versions/a2c4e6f8b002_add_whatsapp_activation_tests.py"
    spec = importlib.util.spec_from_file_location("activation_migration", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_activation_persistence_declares_bounded_and_private_binding():
    table = BillingWhatsAppActivationTest.__table__
    assert BillingWhatsAppActivationTest.__tablename__ == "billing_whatsapp_activation_tests"
    assert "recipient_e164" not in table.c
    assert {"recipient_hmac", "recipient_masked"}.issubset(table.c.keys())
    assert BillingNotificationJob.__table__.c.intent_type.default.arg == "ordinary"
    checks = {constraint.name: str(constraint.sqltext) for constraint in table.constraints if isinstance(constraint, sa.CheckConstraint)}
    assert "consent_revision > 0" in checks["ck_whatsapp_activation_consent_revision_positive"]
    assert "artifact_size > 0" in checks["ck_whatsapp_activation_artifact_size_positive"]
    assert "'cancelled'" in checks["ck_whatsapp_activation_status"]
    unique = {constraint.name for constraint in table.constraints if isinstance(constraint, sa.UniqueConstraint)}
    assert {"uq_whatsapp_activation_actor_key", "uq_whatsapp_activation_batch", "uq_whatsapp_activation_job", "uq_whatsapp_activation_media_token"}.issubset(unique)


def test_activation_migration_fresh_upgrade_creates_constrained_schema(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "activation-fresh.sqlite3")
    command.upgrade(config, ACTIVATION_MIGRATION)
    inspector = sa.inspect(engine)
    assert inspector.has_table("billing_whatsapp_activation_tests")
    assert {"intent_type", "recipient_hmac", "recipient_masked"}.issubset(
        {column["name"] for column in inspector.get_columns("billing_notification_jobs")}
        | {column["name"] for column in inspector.get_columns("billing_whatsapp_activation_tests")}
    )
    assert {"uq_whatsapp_activation_actor_key", "uq_whatsapp_activation_batch", "uq_whatsapp_activation_job", "uq_whatsapp_activation_media_token"}.issubset(
        {item["name"] for item in inspector.get_unique_constraints("billing_whatsapp_activation_tests")}
    )
    assert ("intent_type", "status", "lease_expires_at") in {
        tuple(item["column_names"]) for item in inspector.get_indexes("billing_notification_jobs")
    }
    engine.dispose()


def test_activation_migration_backfills_legacy_jobs_and_refuses_destructive_downgrade(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "activation-legacy.sqlite3")
    command.upgrade(config, PREVIOUS_MIGRATION)
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO billing_notification_jobs (batch_id, teacher_ci, channel, status, attempts, created_at, updated_at) VALUES (1, 'legacy', 'whatsapp', 'queued', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
    command.upgrade(config, ACTIVATION_MIGRATION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT intent_type FROM billing_notification_jobs WHERE id = 1")) == "ordinary"
    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREVIOUS_MIGRATION)
    assert sa.inspect(engine).has_table("billing_whatsapp_activation_tests")
    engine.dispose()


def test_activation_migration_rejects_incompatible_preexisting_adoption(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "activation-adoption.sqlite3")
    command.upgrade(config, PREVIOUS_MIGRATION)
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE billing_whatsapp_activation_tests (id INTEGER PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="Incompatible pre-existing billing_whatsapp_activation_tests columns"):
        command.upgrade(config, ACTIVATION_MIGRATION)
    engine.dispose()


class _PostgreSQLActivationInspector:
    def __init__(self):
        self.bind = type("Bind", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})()
        table = BillingWhatsAppActivationTest.__table__
        self.columns = [{"name": column.name, "type": column.type, "nullable": column.nullable} for column in table.columns]
        self.pk = {"constrained_columns": ["id"]}
        self.foreign_keys = [{"constrained_columns": [item.parent.name], "referred_table": item.column.table.name, "referred_columns": [item.column.name], "options": {"ondelete": item.ondelete}} for foreign_key in table.foreign_key_constraints for item in foreign_key.elements]
        self.indexes = [{"name": "ix_whatsapp_activation_status", "column_names": ["status"]}]

    def get_columns(self, _table): return self.columns
    def get_pk_constraint(self, _table): return self.pk
    def get_unique_constraints(self, _table): return [{"name": item.name, "column_names": [column.name for column in item.columns]} for item in BillingWhatsAppActivationTest.__table__.constraints if isinstance(item, sa.UniqueConstraint)]
    def get_check_constraints(self, _table): return [{"name": item.name, "sqltext": str(item.sqltext)} for item in BillingWhatsAppActivationTest.__table__.constraints if isinstance(item, sa.CheckConstraint)]
    def get_foreign_keys(self, _table): return self.foreign_keys
    def get_indexes(self, _table): return self.indexes


def test_activation_adoption_requires_exact_postgresql_pk_fks_and_indexes():
    module = _migration_module()
    inspector = _PostgreSQLActivationInspector()
    module._validate_activation_table(inspector)
    for attribute, bad, message in (
        ("pk", {"constrained_columns": ["actor_user_id"]}, "primary key"),
        ("indexes", [], "index"),
    ):
        setattr(inspector, attribute, bad)
        with pytest.raises(RuntimeError, match=message):
            module._validate_activation_table(inspector)
        setattr(inspector, attribute, _PostgreSQLActivationInspector().__dict__[attribute])
    for target, action in (("wrong_table", "RESTRICT"), ("users", "CASCADE")):
        bad = [dict(item, options=dict(item["options"])) for item in inspector.foreign_keys]
        bad[0].update(referred_table=target, options={"ondelete": action})
        inspector.foreign_keys = bad
        with pytest.raises(RuntimeError, match="foreign keys"):
            module._validate_activation_table(inspector)
        inspector.foreign_keys = _PostgreSQLActivationInspector().foreign_keys
