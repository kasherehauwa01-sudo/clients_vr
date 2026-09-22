"""Добавить индексы нормализованных менеджеров и клиентов.

Revision ID: 20260921_0014
Revises: 20260828_0013
"""
from alembic import op
import sqlalchemy as sa

revision = "20260921_0014"
down_revision = "20260828_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_clients_manager_normalized",
        "clients",
        [sa.text("lower(trim(manager))")],
        if_not_exists=True,
    )
    op.create_index(
        "ix_clients_name_normalized",
        "clients",
        [sa.text("lower(trim(name))")],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_clients_name_normalized", table_name="clients", if_exists=True)
    op.drop_index("ix_clients_manager_normalized", table_name="clients", if_exists=True)
