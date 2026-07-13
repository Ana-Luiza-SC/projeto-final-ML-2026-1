"""persistencia academica, autenticacao e catalogo
Revision ID: 001_persistence_catalog
"""

from alembic import op
import sqlalchemy as sa

revision = "001_persistence_catalog"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    for name, group in [
        ("disciplines", None),
        ("course_plans", None),
        ("assessment_content_links", None),
        ("complexity_analyses", None),
        ("assessments", "discipline_id"),
        ("absences", "discipline_id"),
        ("content_nodes", "discipline_id"),
    ]:
        cols = [
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(36),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("payload", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        ]
        if group:
            cols.append(sa.Column(group, sa.String(64), nullable=False))
        op.create_table(name, *cols)
        op.create_index(f"ix_{name}_user_id", name, ["user_id"])
        if group:
            op.create_index(f"ix_{name}_{group}", name, [group])
    op.create_table(
        "catalog_components",
        sa.Column("code", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("workload_hours", sa.Integer()),
        sa.Column("academic_unit", sa.String(300)),
        sa.Column("syllabus", sa.Text(), nullable=False),
        sa.Column("current_program", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    for name in [
        "catalog_components",
        "complexity_analyses",
        "assessment_content_links",
        "content_nodes",
        "absences",
        "assessments",
        "course_plans",
        "disciplines",
        "users",
    ]:
        op.drop_table(name)
