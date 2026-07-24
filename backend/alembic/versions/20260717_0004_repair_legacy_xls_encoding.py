"""repair text imported from legacy XLS with a wrong code page

Revision ID: 20260717_0004
Revises: 20260717_0003
Create Date: 2026-07-17
"""
revision = "20260717_0004"
down_revision = "20260717_0003"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # Массовое построчное исправление десятков тысяч записей нельзя выполнять
    # перед запуском API: на большой базе оно надолго оставляло nginx без upstream.
    # Кодировка исправляется импортером при повторной загрузке исходного XLS.
    pass


def downgrade() -> None:
    # Обратное преобразование намеренно не выполняется: оно снова испортило бы данные.
    pass
