"""Отмечает клиентов, повторно импортированных с исходным полем Email.

Revision ID: 20260826_0012
Revises: 20260826_0011
"""
from alembic import op
import sqlalchemy as sa


revision = "20260826_0012"
down_revision = "20260826_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("clients")}
    if "raw_email_source_known" not in columns:
        op.add_column(
            "clients",
            sa.Column("raw_email_source_known", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    # Не выполняем массовый UPDATE 160 000+ клиентов во время старта
    # контейнера. Маркер будет установлен обычным импортом конкретной записи.


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("clients")}
    if "raw_email_source_known" in columns:
        op.drop_column("clients", "raw_email_source_known")
