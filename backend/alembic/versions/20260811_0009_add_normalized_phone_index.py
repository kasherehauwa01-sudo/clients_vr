"""Добавляет индексированный номер телефона для быстрого поиска карточки.

Revision ID: 20260811_0009
Revises: 20260730_0008
"""
from alembic import op
import sqlalchemy as sa


revision = "20260811_0009"
down_revision = "20260730_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("phones", sa.Column("normalized_phone", sa.String(10), nullable=True))
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # regexp_replace обрабатывает и старые форматированные значения без
        # загрузки всей таблицы телефонов в память приложения.
        op.execute(sa.text("""
            UPDATE phones
            SET normalized_phone = right(regexp_replace(phone, '[^0-9]', '', 'g'), 10)
            WHERE length(regexp_replace(phone, '[^0-9]', '', 'g')) >= 10
        """))
    else:
        rows = bind.execute(sa.text("SELECT id, phone FROM phones")).fetchall()
        for phone_id, phone in rows:
            digits = "".join(character for character in (phone or "") if character.isdigit())
            if len(digits) >= 10:
                bind.execute(
                    sa.text("UPDATE phones SET normalized_phone = :phone WHERE id = :id"),
                    {"phone": digits[-10:], "id": phone_id},
                )
    op.create_index("ix_phones_normalized_phone", "phones", ["normalized_phone"])


def downgrade() -> None:
    op.drop_index("ix_phones_normalized_phone", table_name="phones")
    op.drop_column("phones", "normalized_phone")
