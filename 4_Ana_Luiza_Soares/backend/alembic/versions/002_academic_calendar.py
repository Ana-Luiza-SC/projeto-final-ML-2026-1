"""calendario academico
Revision ID: 002_academic_calendar
Revises: 001_persistence_catalog
"""

from alembic import op
import sqlalchemy as sa

revision = "002_academic_calendar"
down_revision = "001_persistence_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "academic_events",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("discipline_id", sa.String(64), nullable=True),
        sa.Column("assessment_id", sa.String(64), nullable=True),
    )
    op.create_index("ix_academic_events_user_id", "academic_events", ["user_id"])
    op.create_index("ix_academic_events_discipline_id", "academic_events", ["discipline_id"])
    op.create_index("ix_academic_events_assessment_id", "academic_events", ["assessment_id"])


def downgrade():
    op.drop_table("academic_events")
