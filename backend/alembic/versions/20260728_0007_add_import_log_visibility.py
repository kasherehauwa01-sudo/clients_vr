"""Добавляет возможность очищать журнал, не удаляя служебные записи импорта.

Revision ID: 20260728_0007
Revises: 20260720_0006
"""

from alembic import op
import sqlalchemy as sa

revision = "20260728_0007"
down_revision = "20260720_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("imports", sa.Column("log_hidden", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_imports_log_hidden", "imports", ["log_hidden"])


def downgrade() -> None:
    op.drop_index("ix_imports_log_hidden", table_name="imports")
    op.drop_column("imports", "log_hidden")
