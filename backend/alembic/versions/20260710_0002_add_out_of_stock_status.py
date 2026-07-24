"""add out_of_stock client status

Revision ID: 20260710_0002
Revises: 20260709_0001
Create Date: 2026-07-10
"""
from alembic import op

revision = "20260710_0002"
down_revision = "20260709_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE clientstatus ADD VALUE IF NOT EXISTS 'out_of_stock'")


def downgrade() -> None:
    # PostgreSQL не поддерживает безопасное удаление значения из ENUM без пересоздания типа.
    pass
