"""Добавляет последовательный журнал изменений клиентов.

Revision ID: 20260813_0010
Revises: 20260811_0009
"""
from alembic import op
import sqlalchemy as sa


revision = "20260813_0010"
down_revision = "20260811_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "client_changes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # Намеренно без FK: tombstone обязан сохраниться после удаления клиента.
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("payload", sa.Text()),
    )
    op.create_index("ix_client_changes_client_id", "client_changes", ["client_id"])
    op.create_index("ix_client_changes_changed_at", "client_changes", ["changed_at"])
    op.create_index("ix_client_changes_operation", "client_changes", ["operation"])


def downgrade() -> None:
    op.drop_table("client_changes")
