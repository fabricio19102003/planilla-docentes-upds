import importlib.util
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, time
from pathlib import Path
from threading import Barrier

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base
from app.models.contract import ContractDocument, ContractLine
from app.models.academic_management import (
    AcademicProgram,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
    AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock,
)
from app.models.designation import Designation
from app.models.teacher import Teacher
from app.services import contract_ledger_service as ledger
from app.services.payroll_schedule_source_service import PayrollScheduleSource

REVISION = "e3a5c7f9b128"
PREDECESSOR = "d2f4a6b8e017"
TABLES = ("contract_documents", "contract_lines")


def _module():
    path = Path(__file__).parents[1] / "alembic/versions/e3a5c7f9b128_add_immutable_contract_ledger.py"
    spec = importlib.util.spec_from_file_location("contract_ledger_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _config(tmp_path, monkeypatch, name):
    backend = Path(__file__).parents[1]
    url = f"sqlite:///{tmp_path / name}"
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    return sa.create_engine(url), config


def test_contract_ledger_fresh_upgrade_constraints_defaults_and_model_parity(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "contract-ledger-fresh.sqlite3")
    command.upgrade(config, REVISION)
    module = _module()
    _metadata, tables = module._schema()
    inspector = sa.inspect(engine)
    for table in tables:
        assert module._validate_table(inspector, table) == []
        model = Base.metadata.tables[table.name]
        assert set(model.c.keys()) == set(table.c.keys())
        assert {item.name for item in model.indexes} == {item.name for item in table.indexes}
        assert {item.name for item in model.constraints if item.name} == {
            item.name for item in table.constraints if item.name
        }
    assert len(inspector.get_foreign_keys("contract_lines")) == 5
    engine.dispose()


def test_contract_ledger_rejects_partial_adoption_before_mutation(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "contract-ledger-partial.sqlite3")
    command.upgrade(config, PREDECESSOR)
    module = _module()
    _metadata, tables = module._schema()
    tables[0].create(engine)
    before = sa.inspect(engine).get_table_names()
    with pytest.raises(RuntimeError, match="Partial contract-ledger adoption"):
        command.upgrade(config, REVISION)
    assert sa.inspect(engine).get_table_names() == before
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREDECESSOR
    engine.dispose()


def test_contract_ledger_adopts_only_complete_exact_schema(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "contract-ledger-compatible.sqlite3")
    command.upgrade(config, PREDECESSOR)
    module = _module()
    metadata, tables = module._schema()
    metadata.create_all(engine, tables=list(tables))
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == REVISION
        triggers = {
            row[0] for row in connection.execute(sa.text(
                "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'trg_contract_%'"
            ))
        }
    assert len(triggers) == 6
    engine.dispose()


def test_contract_ledger_restore_required_downgrade_and_sqlite_immutability(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "contract-ledger-immutable.sqlite3")
    command.upgrade(config, REVISION)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO teachers (ci, full_name, created_at) VALUES "
            "('LEDGER-1', 'Ledger Teacher', CURRENT_TIMESTAMP)"
        ))
        connection.execute(sa.text(
            "INSERT INTO contract_documents "
            "(id, public_id, teacher_ci, teacher_name, teacher_snapshot, academic_period, "
            "period_snapshot, document_kind, amendment_sequence, effective_date, source_digest, "
            "template_version, department, full_snapshot, artifact_filename, artifact_media_type, "
            "artifact_sha256, artifact_size, artifact_content) VALUES "
            "(1, 'ledger-id', 'LEDGER-1', 'Ledger Teacher', '{}', 'I/2026', '{}', 'original', 0, "
            "'2026-01-01', 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', "
            "'v1', 'Pando', '{}', 'contract.pdf', 'application/pdf', "
            "'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', 4, X'25504446')"
        ))
    with pytest.raises(DatabaseError, match="immutable"), engine.begin() as connection:
        connection.execute(sa.text("UPDATE contract_documents SET teacher_name = 'Changed' WHERE id = 1"))
    with pytest.raises(RuntimeError, match="Restore an explicitly approved backup"):
        command.downgrade(config, PREDECESSOR)
    assert set(TABLES).issubset(sa.inspect(engine).get_table_names())
    engine.dispose()


def test_sqlite_contract_ledger_rejects_invalid_lineage_and_mixed_provenance(tmp_path, monkeypatch):
    engine, config = _config(tmp_path, monkeypatch, "contract-ledger-integrity.sqlite3")
    command.upgrade(config, REVISION)
    document_sql = sa.text("""
        INSERT INTO contract_documents
        (id, public_id, teacher_ci, teacher_name, teacher_snapshot, academic_period,
         period_snapshot, document_kind, root_contract_id, predecessor_contract_id,
         amendment_sequence, effective_date, source_digest, template_version, department,
         full_snapshot, artifact_filename, artifact_media_type, artifact_sha256,
         artifact_size, artifact_content)
        VALUES
        (:id, :public_id, 'LEDGER-1', 'Ledger Teacher', '{}', 'I/2026', '{}', :kind,
         :root_id, :predecessor_id, :sequence, '2026-01-01', :digest, 'v1', 'Pando',
         '{}', 'contract.pdf', 'application/pdf', :artifact_digest, 4, X'25504446')
    """)
    with engine.begin() as connection:
        connection.execute(sa.text(
            "INSERT INTO teachers (ci, full_name, created_at) VALUES "
            "('LEDGER-1', 'Ledger Teacher', CURRENT_TIMESTAMP), "
            "('LEDGER-2', 'Other Teacher', CURRENT_TIMESTAMP)"
        ))
        connection.execute(document_sql, {
            "id": 1, "public_id": "root", "kind": "original", "root_id": None,
            "predecessor_id": None, "sequence": 0, "digest": "a" * 64,
            "artifact_digest": "b" * 64,
        })
        connection.execute(document_sql, {
            "id": 2, "public_id": "amendment-1", "kind": "amendment", "root_id": 1,
            "predecessor_id": 1, "sequence": 1, "digest": "c" * 64,
            "artifact_digest": "d" * 64,
        })

    with pytest.raises(DatabaseError, match="lineage"), engine.begin() as connection:
        connection.execute(document_sql, {
            "id": 3, "public_id": "invalid-root", "kind": "amendment", "root_id": 2,
            "predecessor_id": 2, "sequence": 2, "digest": "e" * 64,
            "artifact_digest": "f" * 64,
        })
    with pytest.raises(DatabaseError, match="lineage"), engine.begin() as connection:
        connection.execute(document_sql, {
            "id": 4, "public_id": "skipped", "kind": "amendment", "root_id": 1,
            "predecessor_id": 2, "sequence": 3, "digest": "1" * 64,
            "artifact_digest": "2" * 64,
        })
    with pytest.raises(DatabaseError, match="lineage"), engine.begin() as connection:
        connection.execute(document_sql, {
            "id": 5, "public_id": "self-linked", "kind": "amendment", "root_id": 5,
            "predecessor_id": 5, "sequence": 2, "digest": "3" * 64,
            "artifact_digest": "4" * 64,
        })

    with engine.begin() as connection:
        connection.execute(sa.text("""
            INSERT INTO designations
            (id, teacher_ci, subject, semester, group_code, academic_period, schedule_json,
             designation_type, created_at)
            VALUES (301, 'LEDGER-2', 'Anatomy', 'I', 'M-1', 'I/2026', '[]',
                    'regular', CURRENT_TIMESTAMP)
        """))
        connection.execute(sa.text("""
            INSERT INTO academic_programs (id, code, name, active, created_at, updated_at)
            VALUES (201, 'MED', 'Medicine', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """))
        connection.execute(sa.text("""
            INSERT INTO academic_schedule_drafts
            (id, program_id, academic_period, name, normalized_name, status, created_at, updated_at)
            VALUES
            (301, 201, 'I/2026', 'Draft 1', 'draft-1', 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
            (302, 201, 'I/2026', 'Draft 2', 'draft-2', 'published', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """))
        connection.execute(sa.text("""
            INSERT INTO academic_schedule_publications
            (id, program_id, academic_period, effective_from, sequence, content_digest,
             source_draft_id, created_at)
            VALUES
            (101, 201, 'I/2026', '2026-01-01', 1, :digest1, 301, CURRENT_TIMESTAMP),
            (102, 201, 'I/2026', '2026-03-01', 2, :digest2, 302, CURRENT_TIMESTAMP)
        """), {"digest1": "5" * 64, "digest2": "6" * 64})
        connection.execute(sa.text("""
            INSERT INTO academic_schedule_published_blocks
            (id, publication_id, source_block_id, source_offering_id, source_subject_id,
             source_group_id, source_classroom_id, subject_code, subject_name, group_code,
             semester, classroom_code, classroom_name, activity_type, weekday, start_time, end_time)
            VALUES
            (401, 101, 1, 1, 1, 1, 1, 'ANAT', 'Anatomy', 'M-1', 1, 'A1', 'Room A1',
             'theory', 'monday', '08:00:00', '09:30:00'),
            (402, 102, 2, 1, 1, 1, 1, 'ANAT', 'Anatomy', 'M-1', 1, 'A1', 'Room A1',
             'theory', 'monday', '08:00:00', '09:30:00')
        """))
        connection.execute(sa.text("""
            INSERT INTO academic_schedule_published_assignments
            (id, publication_block_id, source_assignment_id, teacher_ci, teacher_name,
             effective_from, effective_to)
            VALUES (501, 401, 1, 'LEDGER-1', 'Ledger Teacher', '2026-01-01', '2026-06-30')
        """))

    line_sql = sa.text("""
        INSERT INTO contract_lines
        (contract_id, line_number, activity_kind, rate_class, hourly_rate, hours, hour_basis,
         subject_label, group_label, semester_label, schedule_label, effective_from, effective_to,
         source_kind, source_id, designation_id, publication_id, publication_sequence,
         publication_program_id, authority_effective_from, published_block_id,
         published_assignment_id, change_kind)
        VALUES
        (1, :line_number, 'theory', 'regular', 70, 4, 'weekly', 'Anatomy', 'M-1', 'I',
         'monday 08:00-09:30', '2026-01-01', '2026-06-30', :source_kind, :source_id,
         :designation_id, :publication_id, :publication_sequence, :program_id, :authority_date,
         :block_id, :assignment_id, 'full')
    """)
    with pytest.raises(DatabaseError, match="legacy.*provenance"), engine.begin() as connection:
        connection.execute(line_sql, {
            "line_number": 1, "source_kind": "legacy", "source_id": 301,
            "designation_id": 301, "publication_id": None, "publication_sequence": None,
            "program_id": None, "authority_date": "2026-01-01", "block_id": None,
            "assignment_id": None,
        })
    with engine.begin() as connection:
        connection.execute(line_sql, {
            "line_number": 1, "source_kind": "published", "source_id": 501,
            "designation_id": None, "publication_id": 101, "publication_sequence": 1,
            "program_id": 201, "authority_date": "2026-01-01", "block_id": 401,
            "assignment_id": 501,
        })
    with pytest.raises(DatabaseError, match="published.*provenance"), engine.begin() as connection:
        connection.execute(line_sql, {
            "line_number": 2, "source_kind": "published", "source_id": 501,
            "designation_id": None, "publication_id": 102, "publication_sequence": 2,
            "program_id": 201, "authority_date": "2026-03-01", "block_id": 402,
            "assignment_id": 501,
        })
    engine.dispose()


def test_postgresql_contract_ledger_fresh_upgrade_and_alembic_check(monkeypatch):
    url = os.getenv("CONTRACT_LEDGER_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("CONTRACT_LEDGER_TEST_POSTGRES_URL is not configured")
    parsed = sa.engine.make_url(url)
    if parsed.get_backend_name() != "postgresql" or "test" not in (parsed.database or ""):
        pytest.fail("CONTRACT_LEDGER_TEST_POSTGRES_URL must target a dedicated PostgreSQL test database")
    engine = sa.create_engine(url)
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    backend = Path(__file__).parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    command.upgrade(config, "head")
    command.check(config)
    assert set(TABLES).issubset(sa.inspect(engine).get_table_names())

    Session = sessionmaker(bind=engine)
    with Session.begin() as session:
        teacher = Teacher(ci="CONCURRENT-1", full_name="Concurrent Teacher")
        session.add(teacher)
        session.flush()
        designation = Designation(
            teacher_ci=teacher.ci,
            subject="Anatomy",
            semester="I",
            group_code="M-1",
            academic_period="I/2026",
            designation_type="regular",
            schedule_json=[],
        )
        session.add(designation)
        session.flush()
        designation_id = designation.id

    source = PayrollScheduleSource(
        source_kind="legacy",
        source_id=designation_id,
        teacher_ci="CONCURRENT-1",
        subject="Anatomy",
        group_code="M-1",
        semester="I",
        activity_kind="theory",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 6, 30),
        designation_id=designation_id,
        schedule=[{
            "dia": "lunes", "hora_inicio": "08:00", "hora_fin": "09:30",
            "horas_academicas": 2,
        }],
    )
    monkeypatch.setattr(
        ledger,
        "payroll_schedule_sources",
        lambda _db, *, activity_kind, **_kwargs: [source] if activity_kind == "theory" else [],
    )
    barrier = Barrier(2)

    def issue_once():
        with Session() as session:
            barrier.wait()
            return ledger.issue_contract(
                session,
                teacher_ci="CONCURRENT-1",
                academic_period="I/2026",
                department="Pando",
            ).public_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        public_ids = list(pool.map(lambda _index: issue_once(), range(2)))
    assert len(set(public_ids)) == 1
    with Session() as session:
        assert session.query(ContractDocument).count() == 1

    with Session.begin() as session:
        root = session.query(ContractDocument).one()
        valid_amendment = ContractDocument(
            public_id="postgres-valid-amendment",
            teacher_ci=root.teacher_ci,
            teacher_name=root.teacher_name,
            teacher_snapshot=root.teacher_snapshot,
            academic_period=root.academic_period,
            period_snapshot=root.period_snapshot,
            document_kind="amendment",
            root_contract_id=root.id,
            predecessor_contract_id=root.id,
            amendment_sequence=1,
            effective_date=date(2026, 2, 1),
            source_digest="7" * 64,
            template_version="v1",
            department="Pando",
            full_snapshot={},
            artifact_filename="amendment.pdf",
            artifact_media_type="application/pdf",
            artifact_sha256="8" * 64,
            artifact_size=4,
            artifact_content=b"%PDF",
        )
        session.add(valid_amendment)
        session.flush()
        root_id = root.id
        amendment_id = valid_amendment.id

    with pytest.raises(DatabaseError, match="lineage"), Session.begin() as session:
        session.add(ContractDocument(
            public_id="postgres-invalid-lineage",
            teacher_ci="CONCURRENT-1",
            teacher_name="Concurrent Teacher",
            teacher_snapshot={},
            academic_period="I/2026",
            period_snapshot={},
            document_kind="amendment",
            root_contract_id=amendment_id,
            predecessor_contract_id=amendment_id,
            amendment_sequence=2,
            effective_date=date(2026, 3, 1),
            source_digest="9" * 64,
            template_version="v1",
            department="Pando",
            full_snapshot={},
            artifact_filename="invalid.pdf",
            artifact_media_type="application/pdf",
            artifact_sha256="0" * 64,
            artifact_size=4,
            artifact_content=b"%PDF",
        ))

    with Session.begin() as session:
        other = Teacher(ci="CONCURRENT-2", full_name="Other Teacher")
        session.add(other)
        session.flush()
        wrong_designation = Designation(
            teacher_ci=other.ci,
            subject="Anatomy",
            semester="I",
            group_code="M-2",
            academic_period="I/2026",
            designation_type="regular",
            schedule_json=[],
        )
        session.add(wrong_designation)
        session.flush()
        wrong_designation_id = wrong_designation.id

    with pytest.raises(DatabaseError, match="legacy.*provenance"), Session.begin() as session:
        session.add(ContractLine(
            contract_id=root_id,
            line_number=99,
            activity_kind="theory",
            rate_class="regular",
            hourly_rate=70,
            hours=2,
            hour_basis="weekly",
            subject_label="Anatomy",
            group_label="M-2",
            semester_label="I",
            schedule_label="monday 08:00-09:30",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            source_kind="legacy",
            source_id=wrong_designation_id,
            designation_id=wrong_designation_id,
            authority_effective_from=date(2026, 1, 1),
            change_kind="full",
        ))

    with Session.begin() as session:
        program = AcademicProgram(code="PG-LEDGER", name="Postgres Ledger", active=True)
        session.add(program)
        session.flush()
        drafts = [
            AcademicScheduleDraft(
                program_id=program.id,
                academic_period="I/2026",
                name=f"Draft {number}",
                normalized_name=f"draft-{number}",
                status="published",
            )
            for number in (1, 2)
        ]
        session.add_all(drafts)
        session.flush()
        publications = [
            AcademicSchedulePublication(
                program_id=program.id,
                academic_period="I/2026",
                effective_from=effective_from,
                sequence=sequence,
                content_digest=str(sequence) * 64,
                source_draft_id=draft.id,
            )
            for sequence, effective_from, draft in (
                (1, date(2026, 1, 1), drafts[0]),
                (2, date(2026, 3, 1), drafts[1]),
            )
        ]
        session.add_all(publications)
        session.flush()
        blocks = [
            AcademicSchedulePublishedBlock(
                publication_id=publication.id,
                source_block_id=sequence,
                source_offering_id=1,
                source_subject_id=1,
                source_group_id=1,
                source_classroom_id=1,
                subject_code="ANAT",
                subject_name="Anatomy",
                group_code="M-1",
                semester=1,
                classroom_code="A1",
                classroom_name="Room A1",
                activity_type="theory",
                weekday="monday",
                start_time=time(8, 0),
                end_time=time(9, 30),
            )
            for sequence, publication in enumerate(publications, start=1)
        ]
        session.add_all(blocks)
        session.flush()
        assignment = AcademicSchedulePublishedAssignment(
            publication_block_id=blocks[0].id,
            source_assignment_id=1,
            teacher_ci="CONCURRENT-1",
            teacher_name="Concurrent Teacher",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
        )
        session.add(assignment)
        session.flush()
        assignment_id = assignment.id
        mismatched_block_id = blocks[1].id
        mismatched_publication_id = publications[1].id
        program_id = program.id

    with pytest.raises(DatabaseError, match="published.*provenance"), Session.begin() as session:
        session.add(ContractLine(
            contract_id=root_id,
            line_number=100,
            activity_kind="theory",
            rate_class="regular",
            hourly_rate=70,
            hours=2,
            hour_basis="weekly",
            subject_label="Anatomy",
            group_label="M-1",
            semester_label="I",
            schedule_label="monday 08:00-09:30",
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 6, 30),
            source_kind="published",
            source_id=assignment_id,
            publication_id=mismatched_publication_id,
            publication_sequence=2,
            publication_program_id=program_id,
            authority_effective_from=date(2026, 3, 1),
            published_block_id=mismatched_block_id,
            published_assignment_id=assignment_id,
            change_kind="full",
        ))
    engine.dispose()
