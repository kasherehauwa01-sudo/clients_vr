"""Добавляет журнал FTP-импорта.

Revision ID: 20260730_0008
Revises: 20260728_0007
"""
from alembic import op
import sqlalchemy as sa

revision = "20260730_0008"
down_revision = "20260728_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ftp_import_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_ftp_import_events_created_at", "ftp_import_events", ["created_at"])
    op.create_index("ix_ftp_import_events_file_name", "ftp_import_events", ["file_name"])
    op.create_index("ix_ftp_import_events_status", "ftp_import_events", ["status"])


def downgrade() -> None:
    op.drop_table("ftp_import_events")
