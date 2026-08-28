"""Добавляет списки исключений для email-отчётов.

Revision ID: 20260828_0013
Revises: 20260826_0012
"""
from alembic import op
import sqlalchemy as sa

revision = "20260828_0013"
down_revision = "20260826_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "email_report_exclusions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("category", "email", name="uq_email_report_exclusion_category_email"),
    )
    op.create_index("ix_email_report_exclusions_category", "email_report_exclusions", ["category"])
    op.create_index("ix_email_report_exclusions_email", "email_report_exclusions", ["email"])


def downgrade() -> None:
    op.drop_index("ix_email_report_exclusions_email", table_name="email_report_exclusions")
    op.drop_index("ix_email_report_exclusions_category", table_name="email_report_exclusions")
    op.drop_table("email_report_exclusions")
