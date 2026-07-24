"""add fields from the extended client import table

Revision ID: 20260717_0003
Revises: 20260710_0002
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = "20260717_0003"
down_revision = "20260710_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("clients")}
    existing_indexes = {index["name"] for index in inspector.get_indexes("clients")}
    columns = (
        sa.Column("client_source", sa.String(255), nullable=True),
        sa.Column("last_purchase_date", sa.Date(), nullable=True),
        sa.Column("buyer_type", sa.String(120), nullable=True),
        sa.Column("counterparty_type", sa.String(120), nullable=True),
    )
    for column in columns:
        if column.name not in existing_columns:
            op.add_column("clients", column)
        index_name = f"ix_clients_{column.name}"
        if index_name not in existing_indexes:
            op.create_index(index_name, "clients", [column.name])


def downgrade() -> None:
    for name in ("counterparty_type", "buyer_type", "last_purchase_date", "client_source"):
        op.drop_index(f"ix_clients_{name}", table_name="clients")
        op.drop_column("clients", name)
