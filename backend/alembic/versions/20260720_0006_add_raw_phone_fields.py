"""add raw XLS phone fields

Revision ID: 20260720_0006
Revises: 20260717_0005
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa

revision = "20260720_0006"
down_revision = "20260717_0005"
branch_labels = None
depends_on = None


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_column("clients", "raw_common_phones"):
        op.add_column("clients", sa.Column("raw_common_phones", sa.Text(), nullable=True))
    if not _has_column("clients", "raw_sms_phones"):
        op.add_column("clients", sa.Column("raw_sms_phones", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("clients", "raw_sms_phones"):
        op.drop_column("clients", "raw_sms_phones")
    if _has_column("clients", "raw_common_phones"):
        op.drop_column("clients", "raw_common_phones")
