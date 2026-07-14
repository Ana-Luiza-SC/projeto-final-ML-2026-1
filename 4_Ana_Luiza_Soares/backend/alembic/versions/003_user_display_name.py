"""nome de exibicao do usuario

Revision ID: 003_user_display_name
Revises: 002_academic_calendar
"""

from alembic import op
import sqlalchemy as sa

revision = "003_user_display_name"
down_revision = "002_academic_calendar"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(120), nullable=True),
    )


def downgrade():
    op.drop_column("users", "display_name")
