"""Сохраняет линейную историю миграций для API карточки клиента.

Revision ID: 20260811_0009
Revises: 20260730_0008
"""
revision = "20260811_0009"
down_revision = "20260730_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # phones.phone уже нормализуется импортом и имеет B-tree индекс
    # ix_phones_phone из первой миграции. Полный UPDATE таблицы при запуске
    # контейнера задерживал Uvicorn и оставлял nginx без upstream (HTTP 502).
    pass


def downgrade() -> None:
    pass
