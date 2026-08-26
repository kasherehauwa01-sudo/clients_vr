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
    op.add_column(
        "clients",
        sa.Column("raw_email_source_known", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Если raw_email уже успел заполниться после предыдущей миграции, его
    # происхождение достоверно: записать это поле мог только новый импортёр.
    op.execute(sa.text(
        "UPDATE clients SET raw_email_source_known = true WHERE raw_email IS NOT NULL"
    ))


def downgrade() -> None:
    op.drop_column("clients", "raw_email_source_known")
