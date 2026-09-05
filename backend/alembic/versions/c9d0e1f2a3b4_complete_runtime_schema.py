"""complete the Alembic-owned runtime schema

Revision ID: c9d0e1f2a3b4
Revises: b8c4d2e6f901

This revision closes the historical gap where application startup created
newer tables outside Alembic. Existing compatible tables are preserved and
validated before any missing table is created. Incompatible tables abort the
transaction rather than being silently accepted or rewritten.
"""

from __future__ import annotations

from collections.abc import Iterable

from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b8c4d2e6f901"
branch_labels = None
depends_on = None


TARGET_TABLES = (
    "activity_logs",
    "app_settings",
    "billing_publications",
    "notifications",
    "practice_attendance_logs",
    "practice_planilla_outputs",
    "reports",
    "billing_publication_revisions",
)


def _schema() -> tuple[sa.MetaData, dict[str, sa.Table]]:
    metadata = sa.MetaData()

    users = sa.Table(
        "users", metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ci", sa.String(20), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200)),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("teacher_ci", sa.String(20)),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("must_change_password", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("created_by", sa.Integer),
        sa.Column("last_login", sa.DateTime),
        sa.ForeignKeyConstraint(["teacher_ci"], ["teachers.ci"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    sa.Index("ix_users_id", users.c.id)
    sa.Index("ix_users_ci", users.c.ci, unique=True)

    teachers = sa.Table(
        "teachers", metadata,
        sa.Column("ci", sa.String(20), primary_key=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200)),
        sa.Column("phone", sa.String(50)),
        sa.Column("gender", sa.String(20)),
        sa.Column("external_permanent", sa.String(50)),
        sa.Column("academic_level", sa.String(100)),
        sa.Column("profession", sa.String(200)),
        sa.Column("specialty", sa.Text),
        sa.Column("bank", sa.String(100)),
        sa.Column("account_number", sa.String(50)),
        sa.Column("nit", sa.String(50)),
        sa.Column("sap_code", sa.String(50)),
        sa.Column("invoice_retention", sa.String(50)),
        sa.Column("photo_filename", sa.String(255)),
        sa.Column("photo_content_type", sa.String(100)),
        sa.Column("photo_updated_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime),
    )
    sa.Index("ix_teachers_ci", teachers.c.ci)

    designations = sa.Table(
        "designations", metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("teacher_ci", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("semester", sa.String(50), nullable=False),
        sa.Column("group_code", sa.String(20), nullable=False),
        sa.Column("academic_period", sa.String(20), nullable=False),
        sa.Column("schedule_json", sa.JSON, nullable=False),
        sa.Column("semester_hours", sa.Integer),
        sa.Column("monthly_hours", sa.Integer),
        sa.Column("weekly_hours", sa.Integer),
        sa.Column("weekly_hours_calculated", sa.Integer),
        sa.Column("schedule_raw", sa.Text),
        sa.Column("designation_type", sa.String(20), nullable=False),
        sa.Column("contract_start_date", sa.Date),
        sa.Column("contract_end_date", sa.Date),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(["teacher_ci"], ["teachers.ci"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "teacher_ci", "subject", "semester", "group_code", "academic_period",
            name="uq_designation_teacher_subject_semester_group_period",
        ),
    )
    sa.Index("ix_designations_teacher_ci", designations.c.teacher_ci)
    sa.Index("ix_designations_academic_period", designations.c.academic_period)
    sa.Index("ix_designations_designation_type", designations.c.designation_type)

    planilla_outputs = sa.Table(
        "planilla_outputs", metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("generated_at", sa.DateTime, nullable=False),
        sa.Column("file_path", sa.String(500)),
        sa.Column("total_teachers", sa.Integer, nullable=False),
        sa.Column("total_hours", sa.Integer, nullable=False),
        sa.Column("total_payment", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_overrides_json", sa.JSON),
        sa.Column("excluded_days_json", sa.JSON),
        sa.Column("calculation_snapshot", sa.JSON),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("discount_mode", sa.String(20), nullable=False),
        sa.UniqueConstraint("month", "year", name="uq_planilla_month_year"),
    )

    activity_logs = sa.Table(
        "activity_logs", metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer),
        sa.Column("user_ci", sa.String(20)),
        sa.Column("user_name", sa.String(200)),
        sa.Column("user_role", sa.String(20)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("details", sa.JSON),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("ip_address", sa.String(50)),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    for column in (activity_logs.c.user_id, activity_logs.c.user_ci, activity_logs.c.action,
                   activity_logs.c.category, activity_logs.c.created_at):
        sa.Index(f"ix_activity_logs_{column.name}", column)

    app_settings = sa.Table(
        "app_settings", metadata,
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    billing_publications = sa.Table(
        "billing_publications", metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("planilla_type", sa.String(20), nullable=False, server_default="regular"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("total_teachers", sa.Integer, nullable=False),
        sa.Column("total_payment", sa.Float, nullable=False),
        sa.Column("billing_snapshot", sa.JSON),
        sa.Column("published_by", sa.Integer),
        sa.Column("published_at", sa.DateTime),
        sa.Column("unpublished_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("notes", sa.Text),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "month", "year", "planilla_type",
            name="uq_billing_publication_month_year_type",
        ),
        sa.CheckConstraint(
            "planilla_type IN ('regular', 'practice')",
            name="ck_billing_publication_planilla_type",
        ),
    )

    notifications = sa.Table(
        "notifications", metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False),
        sa.Column("reference_month", sa.Integer),
        sa.Column("reference_year", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    sa.Index("ix_notifications_user_id", notifications.c.user_id)

    practice_attendance_logs = sa.Table(
        "practice_attendance_logs", metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("teacher_ci", sa.String(20), nullable=False),
        sa.Column("designation_id", sa.Integer, nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("scheduled_start", sa.Time, nullable=False),
        sa.Column("scheduled_end", sa.Time, nullable=False),
        sa.Column("actual_start", sa.Time),
        sa.Column("actual_end", sa.Time),
        sa.Column("academic_hours", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("observation", sa.Text),
        sa.Column("registered_by", sa.String(20)),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(["teacher_ci"], ["teachers.ci"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["designation_id"], ["designations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["registered_by"], ["users.ci"]),
        sa.UniqueConstraint(
            "teacher_ci", "designation_id", "date", "scheduled_start",
            name="uq_practice_attendance_log",
        ),
    )
    sa.Index("ix_practice_attendance_logs_teacher_ci", practice_attendance_logs.c.teacher_ci)
    sa.Index("ix_practice_attendance_logs_designation_id", practice_attendance_logs.c.designation_id)
    sa.Index("ix_practice_attendance_logs_date", practice_attendance_logs.c.date)

    practice_planilla_outputs = sa.Table(
        "practice_planilla_outputs", metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("generated_at", sa.DateTime, nullable=False),
        sa.Column("file_path", sa.Text),
        sa.Column("total_teachers", sa.Integer, nullable=False),
        sa.Column("total_hours", sa.Integer, nullable=False),
        sa.Column("total_payment", sa.Numeric(12, 2), nullable=False),
        sa.Column("payment_overrides_json", sa.JSON),
        sa.Column("excluded_days_json", sa.JSON),
        sa.Column("calculation_snapshot", sa.JSON),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("discount_mode", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.UniqueConstraint("month", "year", name="uq_practice_planilla_month_year"),
    )
    sa.Index("ix_practice_planilla_outputs_month", practice_planilla_outputs.c.month)
    sa.Index("ix_practice_planilla_outputs_year", practice_planilla_outputs.c.year)

    reports = sa.Table(
        "reports", metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("filters", sa.JSON, nullable=False),
        sa.Column("file_path", sa.String(500)),
        sa.Column("file_size", sa.Integer),
        sa.Column("generated_by", sa.Integer),
        sa.Column("generated_at", sa.DateTime, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"], ondelete="SET NULL"),
    )

    revisions = sa.Table(
        "billing_publication_revisions", metadata,
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("publication_id", sa.Integer, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("calculation_digest", sa.String(64), nullable=False),
        sa.Column("billing_digest", sa.String(64), nullable=False),
        sa.Column("calculation_snapshot", sa.JSON, nullable=False),
        sa.Column("billing_snapshot", sa.JSON, nullable=False),
        sa.Column("created_by", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.ForeignKeyConstraint(["publication_id"], ["billing_publications.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("publication_id", "version", name="uq_billing_revision_version"),
        sa.UniqueConstraint(
            "publication_id", "calculation_digest",
            name="uq_billing_revision_calculation_digest",
        ),
    )
    sa.Index("ix_billing_publication_revisions_publication_id", revisions.c.publication_id)

    tables = {
        table.name: table for table in (
            users, teachers, designations, planilla_outputs, activity_logs, app_settings,
            billing_publications, notifications, practice_attendance_logs,
            practice_planilla_outputs, reports, revisions,
        )
    }
    return metadata, tables


def _type_signature(type_: sa.types.TypeEngine) -> tuple[object, ...]:
    if isinstance(type_, sa.Text):
        return ("text",)
    if isinstance(type_, sa.String):
        return ("string", type_.length)
    if isinstance(type_, sa.Boolean):
        return ("boolean",)
    if isinstance(type_, sa.Integer):
        return ("integer",)
    # PostgreSQL reflects DOUBLE PRECISION as DOUBLE_PRECISION(precision=53),
    # which is also a Numeric subclass. Classify Float first so a model Float
    # remains compatible without relaxing precision/scale checks for NUMERIC.
    if isinstance(type_, sa.Float):
        return ("float",)
    if isinstance(type_, sa.Numeric):
        return ("numeric", type_.precision, type_.scale)
    if isinstance(type_, sa.DateTime):
        return ("datetime",)
    if isinstance(type_, sa.Date):
        return ("date",)
    if isinstance(type_, sa.Time):
        return ("time",)
    if isinstance(type_, sa.JSON):
        return ("json",)
    return (type(type_).__name__.lower(),)


def _column_map(inspector: sa.Inspector, table_name: str) -> dict[str, dict[str, object]]:
    return {column["name"]: column for column in inspector.get_columns(table_name)}


def _validate_columns(
    inspector: sa.Inspector,
    table: sa.Table,
    *,
    allow_missing: bool,
) -> list[str]:
    actual = _column_map(inspector, table.name)
    errors: list[str] = []
    for expected in table.columns:
        reflected = actual.get(expected.name)
        if reflected is None:
            if not allow_missing:
                errors.append(f"missing column {expected.name}")
            continue
        if _type_signature(reflected["type"]) != _type_signature(expected.type):
            errors.append(f"column {expected.name} has incompatible type")
        if not expected.primary_key and bool(reflected["nullable"]) != bool(expected.nullable):
            errors.append(f"column {expected.name} has incompatible nullability")
    return errors


def _constraint_column_sets(items: Iterable[dict[str, object]]) -> set[tuple[str, ...]]:
    return {tuple(item.get("column_names") or ()) for item in items}


def _validate_complete(inspector: sa.Inspector, table: sa.Table) -> list[str]:
    errors = _validate_columns(inspector, table, allow_missing=False)
    actual_pk = tuple(inspector.get_pk_constraint(table.name).get("constrained_columns") or ())
    expected_pk = tuple(column.name for column in table.primary_key.columns)
    if actual_pk != expected_pk:
        errors.append("primary key is incompatible")

    actual_unique = _constraint_column_sets(inspector.get_unique_constraints(table.name))
    for constraint in table.constraints:
        if isinstance(constraint, sa.UniqueConstraint):
            columns = tuple(column.name for column in constraint.columns)
            if columns not in actual_unique:
                errors.append(f"missing unique constraint {constraint.name}")

    actual_indexes = {
        item["name"]: (
            tuple(item.get("column_names") or ()),
            bool(item.get("unique", False)),
        )
        for item in inspector.get_indexes(table.name)
    }
    for index in table.indexes:
        expected_index = (
            tuple(column.name for column in index.columns),
            bool(index.unique),
        )
        if actual_indexes.get(index.name) != expected_index:
            errors.append(f"missing or incompatible index {index.name}")

    expected_checks = {
        constraint.name for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint) and constraint.name
    }
    actual_checks = {item["name"] for item in inspector.get_check_constraints(table.name)}
    for name in expected_checks - actual_checks:
        errors.append(f"missing check constraint {name}")

    expected_fks = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            (constraint.ondelete or "").upper(),
        )
        for constraint in table.foreign_key_constraints
    }
    actual_fks = {
        (
            tuple(item.get("constrained_columns") or ()),
            tuple(
                f"{item.get('referred_table')}.{column}"
                for column in (item.get("referred_columns") or ())
            ),
            str((item.get("options") or {}).get("ondelete") or "").upper(),
        )
        for item in inspector.get_foreign_keys(table.name)
    }
    for foreign_key in expected_fks - actual_fks:
        errors.append(f"missing or incompatible foreign key on {', '.join(foreign_key[0])}")
    return errors


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    if column.name not in _column_map(inspector, table_name):
        op.add_column(table_name, column)


def _complete_core_tables(tables: dict[str, sa.Table]) -> None:
    _add_column_if_missing(
        "users",
        sa.Column("must_change_password", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    _add_column_if_missing("teachers", sa.Column("nit", sa.String(50)))

    for column in (
        sa.Column("academic_period", sa.String(20), nullable=False, server_default="I/2026"),
        sa.Column("designation_type", sa.String(20), nullable=False, server_default="regular"),
        sa.Column("contract_start_date", sa.Date),
        sa.Column("contract_end_date", sa.Date),
    ):
        _add_column_if_missing("designations", column)

    inspector = sa.inspect(op.get_bind())
    designation_indexes = {item["name"] for item in inspector.get_indexes("designations")}
    for name, column in (
        ("ix_designations_academic_period", "academic_period"),
        ("ix_designations_designation_type", "designation_type"),
    ):
        if name not in designation_indexes:
            op.create_index(name, "designations", [column])

    unique_names = {item["name"] for item in inspector.get_unique_constraints("designations")}
    new_unique = "uq_designation_teacher_subject_semester_group_period"
    if new_unique not in unique_names:
        with op.batch_alter_table("designations") as batch_op:
            batch_op.create_unique_constraint(
                new_unique,
                ["teacher_ci", "subject", "semester", "group_code", "academic_period"],
            )
    if "uq_designation_teacher_subject_semester_group" in unique_names:
        with op.batch_alter_table("designations") as batch_op:
            batch_op.drop_constraint(
                "uq_designation_teacher_subject_semester_group",
                type_="unique",
            )

    for column in (
        sa.Column("payment_overrides_json", sa.JSON),
        sa.Column("excluded_days_json", sa.JSON),
        sa.Column("calculation_snapshot", sa.JSON),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
        sa.Column("discount_mode", sa.String(20), nullable=False, server_default="attendance"),
    ):
        _add_column_if_missing("planilla_outputs", column)

    # Validate the full current core contract after additive completion.
    inspector = sa.inspect(op.get_bind())
    for name in ("users", "teachers", "designations", "planilla_outputs"):
        errors = _validate_complete(inspector, tables[name])
        if errors:
            raise RuntimeError(f"Incompatible pre-existing table {name}: " + "; ".join(errors))


def upgrade() -> None:
    _metadata, tables = _schema()
    inspector = sa.inspect(op.get_bind())

    # Inspect every pre-existing target before mutating anything. PostgreSQL DDL
    # is transactional, but this ordering also protects less capable harnesses.
    for name in TARGET_TABLES:
        if inspector.has_table(name):
            errors = _validate_complete(inspector, tables[name])
            if errors:
                raise RuntimeError(f"Incompatible pre-existing table {name}: " + "; ".join(errors))

    for name in ("users", "teachers", "designations", "planilla_outputs"):
        errors = _validate_columns(inspector, tables[name], allow_missing=True)
        if errors:
            raise RuntimeError(f"Incompatible pre-existing table {name}: " + "; ".join(errors))

    _complete_core_tables(tables)

    for name in TARGET_TABLES:
        if not sa.inspect(op.get_bind()).has_table(name):
            tables[name].create(op.get_bind())

    inspector = sa.inspect(op.get_bind())
    for name in TARGET_TABLES:
        errors = _validate_complete(inspector, tables[name])
        if errors:
            raise RuntimeError(f"Runtime schema validation failed for {name}: " + "; ".join(errors))


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade is intentionally blocked: this revision adopts pre-existing runtime tables "
        "without proving that Alembic owns their data. Restore an explicitly approved backup instead."
    )
