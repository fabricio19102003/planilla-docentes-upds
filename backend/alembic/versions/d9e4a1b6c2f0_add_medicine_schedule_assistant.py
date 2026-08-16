"""add isolated medicine schedule assistant tables

Revision ID: d9e4a1b6c2f0
Revises: c4a8d7e2f901
"""
from alembic import op
import sqlalchemy as sa

revision = "d9e4a1b6c2f0"
down_revision = "c4a8d7e2f901"
branch_labels = None
depends_on = None


def _tables() -> list[sa.Table]:
    m = sa.MetaData()
    sa.Table("users", m, sa.Column("id", sa.Integer, primary_key=True))
    version = sa.Table("medicine_schedule_versions", m,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("academic_period", sa.String(50), nullable=False),
        sa.Column("description", sa.Text), sa.Column("workbook_sha256", sa.String(64), nullable=False),
        sa.Column("parser_schema_version", sa.String(50), nullable=False), sa.Column("source_file_path", sa.String(500), nullable=False),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("uploaded_by", sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("activated_by", sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("locked_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False))
    offering = sa.Table("medicine_offerings", m,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.ForeignKey(version.c.id, ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(20), nullable=False), sa.Column("semester", sa.Integer),
        sa.Column("subject_raw", sa.String(300), nullable=False), sa.Column("subject_key", sa.String(300), nullable=False),
        sa.Column("group_code", sa.String(50), nullable=False), sa.Column("shift", sa.String(50)),
        sa.Column("source_sheet", sa.String(200), nullable=False), sa.Column("source_row", sa.Integer, nullable=False),
        sa.Column("raw_payload", sa.JSON, nullable=False))
    meeting = sa.Table("medicine_meetings", m,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("offering_id", sa.ForeignKey(offering.c.id, ondelete="CASCADE"), nullable=False),
        sa.Column("activity", sa.String(50), nullable=False), sa.Column("teacher_raw", sa.String(300)), sa.Column("teacher_key", sa.String(300)),
        sa.Column("day", sa.String(20), nullable=False), sa.Column("start_time", sa.Time, nullable=False), sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("source_cell", sa.String(100), nullable=False), sa.Column("raw_payload", sa.JSON, nullable=False))
    issue = sa.Table("medicine_import_issues", m,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.ForeignKey(version.c.id, ondelete="CASCADE"), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False), sa.Column("code", sa.String(100), nullable=False), sa.Column("message", sa.Text, nullable=False),
        sa.Column("location", sa.JSON, nullable=False), sa.Column("state", sa.String(20), nullable=False),
        sa.Column("accepted_by", sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("accepted_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, nullable=False))
    correction = sa.Table("medicine_corrections", m,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.ForeignKey(version.c.id, ondelete="CASCADE"), nullable=False),
        sa.Column("target_type", sa.String(30), nullable=False), sa.Column("target_id", sa.Integer, nullable=False),
        sa.Column("field_name", sa.String(100), nullable=False), sa.Column("before_value", sa.JSON, nullable=False),
        sa.Column("after_value", sa.JSON, nullable=False), sa.Column("actor_id", sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False))
    event = sa.Table("medicine_version_events", m,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.ForeignKey(version.c.id, ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(30), nullable=False), sa.Column("actor_id", sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("details", sa.JSON, nullable=False), sa.Column("created_at", sa.DateTime, nullable=False))
    simulation = sa.Table("medicine_simulations", m,
        sa.Column("id", sa.Integer, primary_key=True), sa.Column("version_id", sa.ForeignKey(version.c.id, ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False), sa.Column("note", sa.Text), sa.Column("inputs", sa.JSON, nullable=False),
        sa.Column("selected_result", sa.JSON, nullable=False), sa.Column("metrics", sa.JSON, nullable=False), sa.Column("warnings", sa.JSON, nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False), sa.Column("result_hash", sa.String(64), nullable=False),
        sa.Column("engine_version", sa.String(50), nullable=False), sa.Column("created_by", sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False), sa.Column("archived_by", sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("archived_at", sa.DateTime))
    return [version, offering, meeting, issue, correction, event, simulation]


def upgrade() -> None:
    for table in _tables():
        table.create(op.get_bind())
    for table, column in (("medicine_offerings", "version_id"), ("medicine_offerings", "subject_key"), ("medicine_meetings", "offering_id"), ("medicine_meetings", "teacher_key"), ("medicine_import_issues", "version_id"), ("medicine_corrections", "version_id"), ("medicine_version_events", "version_id"), ("medicine_simulations", "version_id")):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index("uq_medicine_schedule_active_version", "medicine_schedule_versions", ["is_active"], unique=True,
                    postgresql_where=sa.text("is_active = true"), sqlite_where=sa.text("is_active = 1"))


def downgrade() -> None:
    for table in reversed(_tables()):
        table.drop(op.get_bind())
