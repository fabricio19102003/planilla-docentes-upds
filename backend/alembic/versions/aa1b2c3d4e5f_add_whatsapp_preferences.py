from alembic import op
import sqlalchemy as sa
revision='aa1b2c3d4e5f'; down_revision='a1b2c3d4e5f6'; branch_labels=None; depends_on=None
def upgrade():
    # Runtime-schema adoption may have already materialized this additive table.
    if 'whatsapp_preferences' not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table('whatsapp_preferences',sa.Column('teacher_ci',sa.String(20),sa.ForeignKey('teachers.ci',ondelete='CASCADE'),primary_key=True),sa.Column('phone_e164',sa.String(16),nullable=False),sa.Column('is_verified',sa.Boolean(),nullable=False),sa.Column('consent_evidence',sa.Text()),sa.Column('consent_revision',sa.Integer(),nullable=False),sa.Column('opt_out_evidence',sa.Text()),sa.Column('opted_out_at',sa.DateTime()))
def downgrade():
    if 'whatsapp_preferences' in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table('whatsapp_preferences')
