"""Сохраняет исходное поле Email карточки клиента.

Revision ID: 20260826_0011
Revises: 20260813_0010
"""
from alembic import op
import sqlalchemy as sa


revision = "20260826_0011"
down_revision = "20260813_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Старые агрегированные emails нельзя безопасно разделить по источнику.
    # Поле заполнится при следующем импорте исходного XLS без ложного backfill.
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("clients")}
    if "raw_email" not in columns:
        op.add_column("clients", sa.Column("raw_email", sa.Text(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("clients")}
    if "raw_email" in columns:
        op.drop_column("clients", "raw_email")
