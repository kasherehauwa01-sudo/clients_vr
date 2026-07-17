"""repair text imported from legacy XLS with a wrong code page

Revision ID: 20260717_0004
Revises: 20260717_0003
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = "20260717_0004"
down_revision = "20260717_0003"
branch_labels = None
depends_on = None


def _repair(value: str | None) -> str | None:
    if not value:
        return value
    try:
        repaired = value.encode("latin1").decode("cp1251")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    original_cyrillic = sum("а" <= char.lower() <= "я" or char.lower() == "ё" for char in value)
    repaired_cyrillic = sum("а" <= char.lower() <= "я" or char.lower() == "ё" for char in repaired)
    return repaired if repaired_cyrillic > original_cyrillic else value


def _repair_table(table_name: str, columns: tuple[str, ...]) -> None:
    bind = op.get_bind()
    table = sa.table(
        table_name,
        sa.column("id", sa.Integer),
        *(sa.column(column, sa.String) for column in columns),
    )
    for row in bind.execute(sa.select(table.c.id, *(table.c[column] for column in columns))):
        changes = {
            column: repaired
            for column in columns
            if (repaired := _repair(getattr(row, column))) != getattr(row, column)
        }
        if changes:
            bind.execute(sa.update(table).where(table.c.id == row.id).values(**changes))


def upgrade() -> None:
    _repair_table(
        "clients",
        ("name", "company", "price_type", "manager", "director", "contact_person", "client_source", "buyer_type", "counterparty_type"),
    )
    _repair_table("trade_places", ("place",))
    # Склеенные многострочные номера длиннее предела E.164 и не могут быть корректными.
    # После повторной загрузки файла импортер создаст отдельную запись для каждого номера.
    bind = op.get_bind()
    phones = sa.table("phones", sa.column("phone", sa.String))
    bind.execute(sa.delete(phones).where(sa.func.length(phones.c.phone) > 16))


def downgrade() -> None:
    # Обратное преобразование намеренно не выполняется: оно снова испортило бы данные.
    pass
