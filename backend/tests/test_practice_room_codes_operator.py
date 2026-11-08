"""End-to-end tests for the practice room codes operator (deploy/operators).

The operator is a one-off production script, so it is loaded by path and driven through its
``main()`` against a throwaway SQLite database that holds a committed copy of the world
(publication 5 with 33 practice blocks, the three wrong rooms and their targets). Every test
gets its own copy of that file, so ``apply`` really commits and ``preview`` really rolls back.
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from datetime import date, time, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

import app.database as app_database
from app.database import Base
from app.models.academic_management import (
    AcademicGroup,
    AcademicProgram,
    AcademicScheduleBlock,
    AcademicScheduleDraft,
    AcademicSchedulePublication,
    AcademicSchedulePublishedAssignment,
    AcademicSchedulePublishedBlock,
    AcademicSubject,
    Classroom,
    SubjectOffering,
    TeacherAvailability,
)
from app.models.activity_log import ActivityLog
from app.models.app_setting import AppSetting
from app.models.classroom_reservation import ClassroomReservation
from app.models.teacher import Teacher
from app.models.user import User
from app.services import academic_schedule_publication_service as publication_service
from app.services.effective_schedule_service import effective_schedule_slots
from app.services.payroll_schedule_source_service import payroll_schedule_sources

OPERATOR_PATH = Path(__file__).resolve().parents[2] / "deploy" / "operators" / "practice_room_codes_2026_11.py"
PERIOD = "II/2026"
SOURCE_DATE = date(2026, 9, 21)
WRONG = ("COB-NUEVO-P3-A1", "COB-ANTIGUO-P3-A20", "COB-ANTIGUO-P4-A26")
TARGET = ("COB-ANTIGUO-P1-A1", "COB-NUEVO-P3-A20", "COB-NUEVO-P4-A26")
# (wrong room, subject code, subject, group, weekday, start, end, teacher, target room)
SPECIAL = [
    ("COB-NUEVO-P3-A1", "ANA1", "Anatomía Humana I", "T-01", "thursday", time(15, 10), time(17, 25), "S1", TARGET[0]),
    ("COB-ANTIGUO-P3-A20", "CIR1", "Introducción a la Cirugía I", "N-01", "wednesday", time(19, 10), time(22, 20), "S2", TARGET[1]),
    ("COB-ANTIGUO-P4-A26", "ANA1", "Anatomía Humana I", "N-02", "friday", time(17, 30), time(19, 55), "S3", TARGET[2]),
]
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]


def _load_operator():
    spec = importlib.util.spec_from_file_location("practice_room_codes_2026_11", OPERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def op():
    return _load_operator()


def _sqlite_engine(path: Path):
    engine = create_engine(f"sqlite:///{path}")

    @event.listens_for(engine, "connect")
    def _no_implicit_transactions(dbapi_connection, _record):
        dbapi_connection.isolation_level = None  # pysqlite otherwise defers BEGIN and breaks SAVEPOINT rollback

    @event.listens_for(engine, "begin")
    def _begin(connection):
        connection.exec_driver_sql("BEGIN")

    return engine


def _build_world(db: Session) -> None:
    db.add(User(ci="ADM1", full_name="Admin", password_hash="x", role="admin", is_active=True))
    db.add(AppSetting(key="ACTIVE_ACADEMIC_PERIOD", value=PERIOD))
    program = AcademicProgram(code="MED", name="Medicina")
    subjects = {
        code: AcademicSubject(code=code, name=name)
        for code, name in (("ANA1", "Anatomía Humana I"), ("CIR1", "Introducción a la Cirugía I"), ("FIS1", "Fisiología I"))
    }
    db.add_all([program, *subjects.values()])
    db.flush()
    offerings = {
        code: SubjectOffering(subject_id=subject.id, program_id=program.id, academic_period=PERIOD,
                              semester=1, practice_hours=40)
        for code, subject in subjects.items()
    }
    db.add_all(offerings.values())
    group_codes = ["T-01", "N-01", "N-02"] + [f"G{i:02d}" for i in range(30)]
    groups = {code: AcademicGroup(program_id=program.id, academic_period=PERIOD, semester=1, shift="T",
                                  code=code, expected_size=30) for code in group_codes}
    db.add_all(groups.values())
    rooms = {}
    for code in (*WRONG, *TARGET, *(f"FIL{i:02d}" for i in range(30))):
        rooms[code] = Classroom(code=code, name=f"Aula {code}", campus="Cobija", capacity=40, classroom_type="classroom")
    for code, name in zip(TARGET, ("Aula 1 (Antiguo, piso 1)", "Aula 20 (Nuevo, piso 3)", "Aula 26 (Nuevo, piso 4)")):
        rooms[code].name = name
    db.add_all(rooms.values())
    draft = AcademicScheduleDraft(program_id=program.id, academic_period=PERIOD, name="Historic",
                                  normalized_name="historic", status="published")
    db.add(draft)
    db.flush()
    publication = AcademicSchedulePublication(
        id=5, program_id=program.id, academic_period=PERIOD, effective_from=SOURCE_DATE,
        sequence=1, content_digest="0" * 64, source_draft_id=draft.id,
    )
    db.add(publication)
    db.flush()
    rows = [
        (room, code, name, group, day, start, end, teacher, 3)
        for room, code, name, group, day, start, end, teacher, _t in SPECIAL
    ]
    for i in range(30):
        rows.append((f"FIL{i:02d}", "FIS1", "Fisiología I", f"G{i:02d}", DAYS[i % 6],
                     time(7 + i // 6, 0), time(8 + i // 6, 0), f"F{i:02d}", None if i % 5 == 0 else 2))
    for index, (room, code, name, group, day, start, end, teacher, hours) in enumerate(rows):
        db.add(Teacher(ci=teacher, full_name=f"Docente {teacher}"))
        db.flush()
        block = AcademicSchedulePublishedBlock(
            publication_id=publication.id, source_block_id=900 + index,
            source_offering_id=offerings[code].id, source_subject_id=subjects[code].id,
            source_group_id=groups[group].id, source_classroom_id=rooms[room].id,
            subject_code=code, subject_name=name, group_code=group, semester=1,
            classroom_code=room, classroom_name=rooms[room].name, activity_type="practice",
            weekday=day, start_time=start, end_time=end, academic_hours=hours,
        )
        db.add(block)
        db.flush()
        db.add(AcademicSchedulePublishedAssignment(
            publication_block_id=block.id, source_assignment_id=800 + index, teacher_ci=teacher,
            teacher_name=f"Docente {teacher}", effective_from=SOURCE_DATE,
        ))
    db.commit()


@pytest.fixture(scope="module")
def template(tmp_path_factory):
    path = tmp_path_factory.mktemp("room-codes-template") / "template.sqlite"
    engine = _sqlite_engine(path)
    import app.models  # noqa: F401  (register every table)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _build_world(db)
    engine.dispose()
    return path


@pytest.fixture
def env(op, template, tmp_path, monkeypatch):
    path = tmp_path / "world.sqlite"
    shutil.copyfile(template, path)
    engine = _sqlite_engine(path)
    monkeypatch.setattr(app_database, "engine", engine)
    monkeypatch.setattr(app_database, "SessionLocal", app_database.sessionmaker(bind=engine))
    yield SimpleNamespace(engine=engine, effective=op.bolivia_today() + timedelta(days=3))
    engine.dispose()


def run(op, capsys, env, mode, effective=None, *extra):
    argv = [mode, "--effective-from", (effective or env.effective).isoformat(), *extra]
    code = op.main(argv)
    return code, capsys.readouterr().out


def dump(engine) -> dict[str, list[str]]:
    with engine.connect() as connection:
        return {table.name: sorted(repr(row) for row in connection.execute(table.select()).all())
                for table in Base.metadata.sorted_tables}


def counts(engine, *tables):
    with engine.connect() as connection:
        return {name: connection.execute(text(f"SELECT COUNT(*) FROM {name}")).scalar() for name in tables}


def mutate(env, fn):
    with Session(env.engine) as db:
        fn(db)
        db.commit()


def published_rows(engine, publication_id):
    """Everything a publication snapshot stores, keyed by block, without surrogate ids."""
    with engine.connect() as connection:
        blocks = connection.execute(text(
            "SELECT id, source_offering_id, source_subject_id, source_group_id, source_classroom_id, subject_code, "
            "subject_name, group_code, semester, classroom_code, classroom_name, activity_type, weekday, "
            "start_time, end_time, academic_hours, notes FROM academic_schedule_published_blocks "
            "WHERE publication_id = :p"), {"p": publication_id}).mappings().all()
        result = {}
        for block in blocks:
            assignments = connection.execute(text(
                "SELECT teacher_ci, teacher_name, effective_from, effective_to "
                "FROM academic_schedule_published_assignments WHERE publication_block_id = :b ORDER BY id"),
                {"b": block["id"]}).mappings().all()
            data = {key: value for key, value in block.items() if key != "id"}
            data["assignments"] = [dict(item) for item in assignments]
            result[(block["group_code"], block["weekday"], block["start_time"])] = data
        return result


# ── Pure comparison ───────────────────────────────────────────────────────────

def _block(**overrides):
    base = {
        "offering_id": 1, "subject_id": 1, "subject_code": "A", "subject_name": "A", "group_id": 1,
        "group_code": "G", "semester": 1, "classroom_id": 10, "classroom_code": "R1", "classroom_name": "Room 1",
        "activity_type": "practice", "weekday": "monday", "start_time": "08:00:00", "end_time": "09:00:00",
        "academic_hours": 2, "notes": None,
        "assignments": [{"teacher_ci": "T", "teacher_name": "T", "effective_from": "2026-09-21", "effective_to": None}],
    }
    return {**base, **overrides}


def test_compare_blocks_accepts_only_the_expected_room_moves(op):
    old = [_block(), _block(group_code="H", classroom_id=11, classroom_code="R2", classroom_name="Room 2")]
    new = [_block(), _block(group_code="H", classroom_id=12, classroom_code="R3", classroom_name="Room 3")]
    moves = {("a", "h", 1, "practice", "monday", "08:00:00", "09:00:00"): ("R3", "Room 3")}
    assert op.compare_blocks(old, new, moves) == []


@pytest.mark.parametrize("change", [
    {"academic_hours": 3},
    {"assignments": []},
    {"classroom_code": "R9"},
    {"subject_name": "B"},
])
def test_compare_blocks_reports_any_other_difference(op, change):
    assert op.compare_blocks([_block()], [_block(**change)], {})


def test_compare_blocks_reports_a_missing_or_wrong_move_and_a_count_change(op):
    old = [_block(group_code="H")]
    moves = {("a", "h", 1, "practice", "monday", "08:00:00", "09:00:00"): ("R3", "Room 3")}
    assert op.compare_blocks(old, old, moves)  # the move did not happen
    assert op.compare_blocks(old, [], {})


# ── fingerprint ───────────────────────────────────────────────────────────────

def _fingerprint(output):
    entries = {}
    for line in output.splitlines():
        if "  rows=" in line:
            digest, rest = line.split("  rows=", 1)
            count, name = rest.split(None, 1)
            entries[name.strip()] = (digest.strip(), int(count))
    return entries


def test_fingerprint_is_read_only_and_stable(op, env, capsys):
    before = dump(env.engine)
    code, first = run(op, capsys, env, "fingerprint")
    _code, second = run(op, capsys, env, "fingerprint")
    assert code == 0
    assert dump(env.engine) == before
    assert _fingerprint(first) == _fingerprint(second)
    names = " ".join(_fingerprint(first))
    for expected in ("publication 5", "academic_schedule_publications", "academic_schedule_published_blocks",
                     "academic_schedule_published_assignments", "practice_attendance_logs",
                     "practice_planilla_outputs", "billing_publications"):
        assert expected in names


# ── preview ───────────────────────────────────────────────────────────────────

def test_preview_prints_the_plan_and_leaves_the_database_untouched(op, env, capsys):
    before = dump(env.engine)
    _code, fp_before = run(op, capsys, env, "fingerprint")
    code, out = run(op, capsys, env, "preview")
    assert code == 0, out
    assert "PREVIEW ONLY" in out
    for wrong, target in zip(WRONG, TARGET):
        assert wrong in out and target in out
    assert "no other difference" in out.lower()
    assert dump(env.engine) == before
    _code, fp_after = run(op, capsys, env, "fingerprint")
    assert _fingerprint(fp_after) == _fingerprint(fp_before)


# ── apply ─────────────────────────────────────────────────────────────────────

def test_apply_moves_exactly_the_three_blocks_and_nothing_else(op, env, capsys):
    old = published_rows(env.engine, 5)
    pubs_before = counts(env.engine, "academic_schedule_publications")["academic_schedule_publications"]
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out
    assert "APPLIED" in out
    with env.engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT id, effective_from, sequence FROM academic_schedule_publications WHERE id <> 5")).all()
    assert len(rows) == 1 and pubs_before == 1
    new_id, effective, _sequence = rows[0]
    assert str(effective)[:10] == env.effective.isoformat()
    new = published_rows(env.engine, new_id)
    assert published_rows(env.engine, 5) == old  # publication 5 is immutable
    assert len(new) == 33 and set(new) == set(old)
    with Session(env.engine) as db:
        targets = {c.code: c for c in db.query(Classroom).filter(Classroom.code.in_(TARGET))}
    moved = {}
    for key, block in old.items():
        if block["classroom_code"] in WRONG:
            moved[key] = targets[TARGET[WRONG.index(block["classroom_code"])]]
    assert len(moved) == 3
    for key, block in old.items():
        expected = dict(block)
        if key in moved:
            expected.update(classroom_code=moved[key].code, classroom_name=moved[key].name,
                            source_classroom_id=moved[key].id)
        assert new[key] == expected, key


def test_apply_deactivates_the_wrong_rooms_with_an_audit_row_each(op, env, capsys):
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out
    with Session(env.engine) as db:
        active = {c.code: c.active for c in db.query(Classroom).filter(Classroom.code.in_((*WRONG, *TARGET)))}
        audit = db.query(ActivityLog).filter(ActivityLog.action == "deactivate_classroom").all()
        admin = db.query(User).filter(User.ci == "ADM1").one()
    assert [active[c] for c in WRONG] == [False, False, False]
    assert [active[c] for c in TARGET] == [True, True, True]
    assert len(audit) == 3
    assert {a.category for a in audit} == {"academic_management"}
    assert {a.user_id for a in audit} == {admin.id}
    assert {a.description for a in audit} == {"Aula desactivado"}
    with Session(env.engine) as db:
        actions = [a.action for a in db.query(ActivityLog).order_by(ActivityLog.id)]
    assert actions.count("clone_academic_schedule_draft") == 1
    assert actions.count("update_academic_schedule_block") == 3
    assert actions.count("publish_academic_schedule_publication") == 1


def test_apply_published_resolution_switches_at_the_effective_date(op, env, capsys):
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out
    with Session(env.engine) as db:
        new_id = db.query(AcademicSchedulePublication.id).filter(AcademicSchedulePublication.id != 5).scalar()
        before = effective_schedule_slots(db, PERIOD, env.effective - timedelta(days=1), include_practice=True)
        after = effective_schedule_slots(db, PERIOD, env.effective, include_practice=True)
    assert {s.publication_id for s in before if s.source_type == "published"} == {5}
    assert {s.publication_id for s in after if s.source_type == "published"} == {new_id}
    assert len([s for s in after if s.source_type == "published"]) == 33


def test_apply_computes_the_expected_blockers_from_the_data(op, env, capsys):
    def add_availability(db):
        db.add(TeacherAvailability(teacher_ci="F01", academic_period=PERIOD, weekday="tuesday",
                                   start_time=time(6, 0), end_time=time(23, 0)))
    mutate(env, add_availability)
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out
    assert "draft_validation x32" in out


def test_apply_twice_is_a_no_op(op, env, capsys):
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out
    after_first = dump(env.engine)
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out
    assert dump(env.engine) == after_first
    assert "already" in out.lower()


def test_apply_reuses_an_existing_draft_of_the_operator(op, env, capsys):
    with Session(env.engine) as db:
        publication_service.clone_publication(db, 5, op.draft_name(env.effective))
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out
    with Session(env.engine) as db:
        drafts = db.query(AcademicScheduleDraft).filter(AcademicScheduleDraft.name == op.draft_name(env.effective)).all()
        assert len(drafts) == 1 and drafts[0].status == "published"
        assert db.query(AcademicSchedulePublication).filter(AcademicSchedulePublication.source_draft_id == drafts[0].id).count() == 1


# ── fail closed: nothing is written ───────────────────────────────────────────

def assert_aborted(op, env, capsys, before, *fragments, mode="apply", effective=None):
    code, out = run(op, capsys, env, mode, effective)
    assert code == 1, out
    for fragment in fragments:
        assert fragment in out, out
    assert dump(env.engine) == before


@pytest.mark.parametrize("days", [0, -1])
def test_effective_date_must_be_strictly_in_the_future(op, env, capsys, days):
    before = dump(env.engine)
    assert_aborted(op, env, capsys, before, "estrictamente posterior", effective=op.bolivia_today() + timedelta(days=days))


def test_missing_target_classroom_names_the_catalog_sync(op, env, capsys):
    mutate(env, lambda db: db.query(Classroom).filter(Classroom.code == TARGET[2]).delete())
    assert_aborted(op, env, capsys, dump(env.engine), TARGET[2], "sincronización del catálogo")


def test_inactive_or_too_small_target_classroom_aborts(op, env, capsys):
    mutate(env, lambda db: db.query(Classroom).filter(Classroom.code == TARGET[0]).update({"capacity": 10}))
    assert_aborted(op, env, capsys, dump(env.engine), TARGET[0], "capacidad")
    mutate(env, lambda db: db.query(Classroom).filter(Classroom.code == TARGET[0]).update({"capacity": 40, "active": False}))
    assert_aborted(op, env, capsys, dump(env.engine), TARGET[0], "inactiva")


def test_missing_source_block_aborts(op, env, capsys):
    def drop(db):
        block = db.query(AcademicSchedulePublishedBlock).filter(
            AcademicSchedulePublishedBlock.publication_id == 5,
            AcademicSchedulePublishedBlock.classroom_code == WRONG[1]).one()
        db.delete(block)
    mutate(env, drop)
    assert_aborted(op, env, capsys, dump(env.engine), WRONG[1], "exactamente")


def test_duplicated_source_block_aborts(op, env, capsys):
    def duplicate(db):
        block = db.query(AcademicSchedulePublishedBlock).filter(
            AcademicSchedulePublishedBlock.publication_id == 5,
            AcademicSchedulePublishedBlock.classroom_code == WRONG[0]).one()
        db.add(AcademicSchedulePublishedBlock(
            publication_id=5, source_block_id=7777, source_offering_id=block.source_offering_id,
            source_subject_id=block.source_subject_id, source_group_id=block.source_group_id,
            source_classroom_id=block.source_classroom_id, subject_code=block.subject_code,
            subject_name=block.subject_name, group_code=block.group_code, semester=block.semester,
            classroom_code=block.classroom_code, classroom_name=block.classroom_name,
            activity_type="practice", weekday=block.weekday, start_time=block.start_time,
            end_time=block.end_time, academic_hours=block.academic_hours))
    mutate(env, duplicate)
    assert_aborted(op, env, capsys, dump(env.engine), WRONG[0], "exactamente")


def test_a_wrong_code_used_by_another_block_aborts(op, env, capsys):
    mutate(env, lambda db: db.query(AcademicSchedulePublishedBlock).filter(
        AcademicSchedulePublishedBlock.classroom_code == "FIL03").update({"classroom_code": WRONG[0]}))
    assert_aborted(op, env, capsys, dump(env.engine), WRONG[0], "otro bloque")


def test_active_period_must_be_ii_2026(op, env, capsys):
    mutate(env, lambda db: db.query(AppSetting).update({"value": "I/2027"}))
    assert_aborted(op, env, capsys, dump(env.engine), "II/2026")


def test_publication_5_must_be_the_latest_publication(op, env, capsys):
    def later(db):
        draft = AcademicScheduleDraft(program_id=1, academic_period=PERIOD, name="Other", normalized_name="other", status="published")
        db.add(draft)
        db.flush()
        db.add(AcademicSchedulePublication(program_id=1, academic_period=PERIOD, effective_from=SOURCE_DATE + timedelta(days=7),
                                           sequence=1, content_digest="1" * 64, source_draft_id=draft.id))
    mutate(env, later)
    assert_aborted(op, env, capsys, dump(env.engine), "última publicación")


def test_a_publication_that_is_not_ours_on_the_requested_date_aborts(op, env, capsys):
    def same_day(db):
        draft = AcademicScheduleDraft(program_id=1, academic_period=PERIOD, name="Other", normalized_name="other", status="published")
        db.add(draft)
        db.flush()
        db.add(AcademicSchedulePublication(program_id=1, academic_period=PERIOD, effective_from=env.effective,
                                           sequence=1, content_digest="1" * 64, source_draft_id=draft.id))
    mutate(env, same_day)
    assert_aborted(op, env, capsys, dump(env.engine), "última publicación")


def test_an_unexpected_difference_in_the_clone_aborts_before_publishing(op, env, capsys, monkeypatch):
    original = op.move_step

    def move_and_tamper(db, draft, *args, **kwargs):
        result = original(db, draft, *args, **kwargs)
        block = db.query(AcademicScheduleBlock).filter(
            AcademicScheduleBlock.draft_id == draft.id, AcademicScheduleBlock.academic_hours == 2).first()
        block.academic_hours = 9
        db.flush()
        return result

    monkeypatch.setattr(op, "move_step", move_and_tamper)
    assert_aborted(op, env, capsys, dump(env.engine), "difiere", "academic_hours")


def test_an_unexpected_publication_blocker_aborts(op, env, capsys, monkeypatch):
    original = publication_service.preview_publication

    def with_extra_blocker(*args, **kwargs):
        preview = original(*args, **kwargs)
        preview["blockers"].append({"category": "regular_planilla", "count": 1,
                                    "message": "Existen 1 registros de planillas regulares en el rango afectado."})
        return preview

    monkeypatch.setattr(publication_service, "preview_publication", with_extra_blocker)
    assert_aborted(op, env, capsys, dump(env.engine), "bloqueos", "regular_planilla")


def test_a_different_availability_count_is_not_tolerated(op, env, capsys, monkeypatch):
    original = publication_service.preview_publication

    def wrong_count(*args, **kwargs):
        preview = original(*args, **kwargs)
        for blocker in preview["blockers"]:
            blocker["count"] -= 1
        return preview

    monkeypatch.setattr(publication_service, "preview_publication", wrong_count)
    assert_aborted(op, env, capsys, dump(env.engine), "bloqueos")


def test_an_active_draft_referencing_a_wrong_room_aborts_before_deactivating(op, env, capsys):
    def other_draft(db):
        draft = AcademicScheduleDraft(program_id=1, academic_period=PERIOD, name="Borrador ajeno", normalized_name="borrador ajeno", status="draft")
        db.add(draft)
        db.flush()
        block = db.query(AcademicSchedulePublishedBlock).filter(AcademicSchedulePublishedBlock.classroom_code == "FIL00").one()
        room = db.query(Classroom).filter(Classroom.code == WRONG[2]).one()
        db.add(AcademicScheduleBlock(draft_id=draft.id, offering_id=block.source_offering_id, group_id=block.source_group_id,
                                     classroom_id=room.id, activity_type="practice", weekday="monday",
                                     start_time=time(20, 0), end_time=time(21, 0), academic_hours=1))
    mutate(env, other_draft)
    assert_aborted(op, env, capsys, dump(env.engine), "Borrador ajeno", WRONG[2])


def test_an_unknown_admin_user_aborts(op, env, capsys):
    before = dump(env.engine)
    code, out = run(op, capsys, env, "apply", None, "--admin-user-id", "9999")
    assert code == 1 and "administrador" in out
    assert dump(env.engine) == before


# ── Target rooms must be free (S5, fail closed) ───────────────────────────────

def first_weekday(on_or_after: date, weekday: int) -> date:
    return on_or_after + timedelta(days=(weekday - on_or_after.weekday()) % 7)


def reserve(env, room_code, day, start, end):
    def add(db):
        room = db.query(Classroom).filter(Classroom.code == room_code).one()
        db.add(ClassroomReservation(
            classroom_id=room.id, teacher_ci="S1", reservation_date=day, start_time=start, end_time=end,
            academic_periods=1, status="confirmed"))
    mutate(env, add)


def test_a_confirmed_reservation_overlapping_a_target_room_slot_aborts(op, env, capsys):
    reserve(env, TARGET[0], first_weekday(env.effective, 3), time(15, 30), time(16, 50))
    before = dump(env.engine)
    for mode in ("preview", "apply"):
        assert_aborted(op, env, capsys, before, TARGET[0], "reserva", mode=mode)


def test_a_reservation_before_the_effective_date_or_cancelled_does_not_block(op, env, capsys):
    reserve(env, TARGET[0], first_weekday(env.effective, 3) - timedelta(days=7), time(15, 30), time(16, 50))
    reserve(env, TARGET[0], first_weekday(env.effective, 4), time(15, 30), time(16, 50))  # another weekday
    mutate(env, lambda db: db.add(ClassroomReservation(
        classroom_id=db.query(Classroom).filter(Classroom.code == TARGET[0]).one().id, teacher_ci="S1",
        reservation_date=first_weekday(env.effective, 3), start_time=time(15, 30), end_time=time(16, 50),
        academic_periods=1, status="cancelled")))
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out


def test_a_back_to_back_reservation_is_allowed(op, env, capsys):
    reserve(env, TARGET[0], first_weekday(env.effective, 3), time(17, 25), time(18, 10))
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out


def test_a_class_of_another_program_in_a_target_room_aborts(op, env, capsys):
    def other_program(db):
        program = AcademicProgram(code="ENF", name="Enfermería")
        db.add(program)
        db.flush()
        draft = AcademicScheduleDraft(program_id=program.id, academic_period=PERIOD, name="Enf",
                                      normalized_name="enf", status="published")
        db.add(draft)
        db.flush()
        publication = AcademicSchedulePublication(
            program_id=program.id, academic_period=PERIOD, effective_from=SOURCE_DATE, sequence=1,
            content_digest="2" * 64, source_draft_id=draft.id)
        db.add(publication)
        db.flush()
        db.add(AcademicSchedulePublishedBlock(
            publication_id=publication.id, source_block_id=1, source_offering_id=1, source_subject_id=1,
            source_group_id=1, source_classroom_id=1, subject_code="ENF1", subject_name="Enfermería I",
            group_code="E-01", semester=1, classroom_code=TARGET[1], classroom_name="x",
            activity_type="theory", weekday="wednesday", start_time=time(20, 0), end_time=time(21, 0)))
    mutate(env, other_program)
    assert_aborted(op, env, capsys, dump(env.engine), TARGET[1], "Enfermería I")


def test_a_block_of_publication_5_already_in_a_target_room_aborts(op, env, capsys):
    mutate(env, lambda db: db.query(AcademicSchedulePublishedBlock).filter(
        AcademicSchedulePublishedBlock.group_code == "G03").update(
        {"classroom_code": TARGET[0], "start_time": time(15, 30), "end_time": time(16, 30)}))
    assert_aborted(op, env, capsys, dump(env.engine), TARGET[0], "Fisiología I")


# ── More fail-closed behaviour ────────────────────────────────────────────────

def test_a_crash_mid_apply_leaves_the_database_unchanged(op, env, capsys, monkeypatch):
    original, calls = op.academic.deactivate_entity, []

    def crash_on_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("boom")
        return original(*args, **kwargs)

    monkeypatch.setattr(op.academic, "deactivate_entity", crash_on_second)
    before = dump(env.engine)
    with pytest.raises(RuntimeError):
        run(op, capsys, env, "apply")
    assert dump(env.engine) == before


def test_rerunning_apply_with_another_date_aborts_without_writes(op, env, capsys):
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out
    assert_aborted(op, env, capsys, dump(env.engine), effective=env.effective + timedelta(days=1))


def _note(db):
    db.query(AcademicSchedulePublishedBlock).filter(AcademicSchedulePublishedBlock.group_code == "G01").update(
        {"notes": "nota"})


def _teacher_name(db):
    db.query(AcademicSchedulePublishedAssignment).filter(
        AcademicSchedulePublishedAssignment.teacher_ci == "F02").update({"teacher_name": "Otro nombre"})


def _ended_assignment(db):
    assignment = db.query(AcademicSchedulePublishedAssignment).filter(
        AcademicSchedulePublishedAssignment.teacher_ci == "F02").one()
    assignment.effective_to = date(2026, 10, 1)
    db.add(AcademicSchedulePublishedAssignment(
        publication_block_id=assignment.publication_block_id, source_assignment_id=5000, teacher_ci="F03",
        teacher_name="Docente F03", effective_from=date(2026, 10, 2)))


@pytest.mark.parametrize("tamper", [_note, _teacher_name, _ended_assignment])
def test_publication_5_details_the_draft_cannot_reproduce_abort_the_preview(op, env, capsys, tamper):
    mutate(env, tamper)
    assert_aborted(op, env, capsys, dump(env.engine), "difiere", mode="preview")


# ── Payroll sources do not move before the effective date ─────────────────────

def _sources(env, start, end):
    with Session(env.engine) as db:
        return payroll_schedule_sources(
            db, academic_period=PERIOD, period_start=start, period_end=end, activity_kind="practice",
            explicit_cutoff=True)


def _signature(sources):
    return [(s.source_key, s.teacher_ci, s.subject, s.group_code,
             [(p.date, p.scheduled_start, p.scheduled_end, p.academic_hours) for p in s.payable_slots])
            for s in sources]


def test_payroll_sources_before_the_effective_date_are_identical_and_hours_are_preserved(op, env, capsys):
    windows = [(date(2026, 10, 1), date(2026, 10, 31)), (SOURCE_DATE, env.effective - timedelta(days=1))]
    spanning = (date(2026, 10, 1), env.effective + timedelta(days=20))
    before = [_signature(_sources(env, *w)) for w in windows]
    hours_before = sum(p.academic_hours for s in _sources(env, *spanning) for p in s.payable_slots)
    code, out = run(op, capsys, env, "apply")
    assert code == 0, out
    assert [_signature(_sources(env, *w)) for w in windows] == before
    assert sum(p.academic_hours for s in _sources(env, *spanning) for p in s.payable_slots) == hours_before > 0
