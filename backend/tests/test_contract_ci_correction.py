"""Issued contracts follow a CI correction, but stay immutable otherwise.

Runs against a database migrated to head, so the real immutability triggers apply.
"""
import os
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from app.config import settings
from app.services.teacher_identity_service import TeacherIdentityService


def _migrated_engine(tmp_path, monkeypatch):
    url = os.getenv("CONTRACT_CI_TEST_POSTGRES_URL") or f"sqlite:///{tmp_path / 'contracts.sqlite'}"
    engine = sa.create_engine(url)
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    command.upgrade(config, "head")
    return engine


def _seed(connection):
    connection.execute(sa.text(
        "INSERT INTO teachers (ci, full_name, created_at) VALUES ('111', 'Docente', CURRENT_TIMESTAMP)"
    ))
    common = {
        "teacher_ci": "111", "teacher_name": "Docente", "snap": "{}", "period": "II/2026",
        "effective_date": date(2026, 8, 1), "digest": "0" * 64, "template": "v1", "dept": "medicina",
        "fname": "c.pdf", "media": "application/pdf", "sha": "0" * 64, "content": b"%PDF",
    }
    insert = sa.text(
        "INSERT INTO contract_documents (id, public_id, teacher_ci, teacher_name, teacher_snapshot, "
        "academic_period, period_snapshot, document_kind, root_contract_id, predecessor_contract_id, "
        "amendment_sequence, effective_date, issued_at, source_digest, template_version, status, "
        "department, full_snapshot, artifact_filename, artifact_media_type, artifact_sha256, "
        "artifact_size, artifact_content) VALUES (:id, :public_id, :teacher_ci, :teacher_name, :snap, "
        ":period, :snap, :kind, :root, :predecessor, :sequence, :effective_date, CURRENT_TIMESTAMP, "
        ":digest, :template, 'issued', :dept, :snap, :fname, :media, :sha, 4, :content)"
    )
    connection.execute(insert, {**common, "id": 1, "public_id": "p-1", "kind": "original",
                                "root": None, "predecessor": None, "sequence": 0})
    connection.execute(insert, {**common, "id": 2, "public_id": "p-2", "kind": "amendment",
                                "root": 1, "predecessor": 1, "sequence": 1, "digest": "1" * 64})


def _contracts(connection):
    return connection.execute(sa.text(
        "SELECT id, teacher_ci, teacher_name, artifact_sha256 FROM contract_documents ORDER BY id"
    )).all()


def test_ci_correction_moves_issued_contracts_and_records_it(tmp_path, monkeypatch):
    engine = _migrated_engine(tmp_path, monkeypatch)
    with engine.begin() as connection:
        _seed(connection)

    with Session(engine) as db:
        TeacherIdentityService(db).change_ci("111", "222", corrected_by=None)
        db.commit()

    with engine.connect() as connection:
        assert _contracts(connection) == [(1, "222", "Docente", "0" * 64), (2, "222", "Docente", "0" * 64)]
        assert connection.execute(sa.text(
            "SELECT old_ci, new_ci, contract_count FROM contract_ci_corrections"
        )).all() == [("111", "222", 2)]
        assert connection.scalar(sa.text("SELECT count(*) FROM teachers WHERE ci = '111'")) == 0


def test_contracts_stay_immutable_outside_a_ci_correction(tmp_path, monkeypatch):
    engine = _migrated_engine(tmp_path, monkeypatch)
    with engine.begin() as connection:
        _seed(connection)
        connection.execute(sa.text(
            "INSERT INTO teachers (ci, full_name, created_at) VALUES ('222', 'Otro', CURRENT_TIMESTAMP)"
        ))

    attempts = [
        "UPDATE contract_documents SET teacher_ci = '222' WHERE id = 1",
        "UPDATE contract_documents SET teacher_name = 'Cambiado' WHERE id = 1",
        "DELETE FROM contract_documents WHERE id = 2",
    ]
    for statement in attempts:
        with pytest.raises(sa.exc.DBAPIError, match="issued contracts are immutable"):
            with engine.begin() as connection:
                connection.execute(sa.text(statement))

    with engine.connect() as connection:
        assert [row[1:3] for row in _contracts(connection)] == [("111", "Docente"), ("111", "Docente")]


def test_grant_does_not_allow_changing_other_columns(tmp_path, monkeypatch):
    engine = _migrated_engine(tmp_path, monkeypatch)
    with engine.begin() as connection:
        _seed(connection)

    with pytest.raises(sa.exc.DBAPIError, match="issued contracts are immutable"):
        with engine.begin() as connection:
            connection.execute(sa.text(
                "INSERT INTO teachers (ci, full_name, created_at) VALUES ('222', 'D', CURRENT_TIMESTAMP)"
            ))
            connection.execute(sa.text(
                "INSERT INTO contract_ci_corrections (old_ci, new_ci, contract_count) VALUES ('111', '222', 2)"
            ))
            connection.execute(sa.text(
                "UPDATE contract_documents SET teacher_ci = '222', teacher_name = 'Otro' WHERE id = 1"
            ))
