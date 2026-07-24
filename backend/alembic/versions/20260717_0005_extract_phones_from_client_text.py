"""extract phone numbers from client text fields

Revision ID: 20260717_0005
Revises: 20260717_0004
Create Date: 2026-07-17
"""
revision = "20260717_0005"
down_revision = "20260717_0004"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Извлечение телефонов выполняется во время импорта. Полный обход рабочей
    # базы в стартовой миграции блокировал запуск Uvicorn и приводил к 502.
    pass


def downgrade() -> None:
    # Невозможно отличить найденные номера от ранее импортированных без потери данных.
    pass
