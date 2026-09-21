from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Client, ClientStatus

router = APIRouter(prefix="/api", tags=["sales-journal"])


def _normalized(column):
    """SQL-выражение для удаления внешних пробелов из текстового поля."""
    return func.trim(column)


def _non_empty(column):
    return column.is_not(None), func.length(_normalized(column)) > 0


def managers_query():
    """Собирает одно отображаемое значение для каждого менеджера без учёта регистра."""
    manager = _normalized(Client.manager)
    return (
        select(func.min(manager).label("manager"))
        .where(Client.status != ClientStatus.archived, *_non_empty(Client.manager))
        .group_by(func.lower(manager))
        .order_by(func.lower(func.min(manager)), func.min(manager))
    )


def manager_clients_query(manager_name: str):
    """Возвращает уникальные активные наименования клиентов выбранного менеджера."""
    client_name = _normalized(Client.name)
    normalized_manager = _normalized(Client.manager)
    return (
        select(func.min(client_name).label("client_name"))
        .where(
            Client.status != ClientStatus.archived,
            *_non_empty(Client.name),
            func.lower(normalized_manager) == manager_name.strip().lower(),
        )
        .group_by(func.lower(client_name))
        .order_by(func.lower(func.min(client_name)), func.min(client_name))
    )


@router.get("/managers", response_model=list[str])
def sales_journal_managers(db: Session = Depends(get_db)) -> list[str]:
    return list(db.scalars(managers_query()).all())


def sales_journal_clients(manager_name: str, db: Session) -> list[str]:
    return list(db.scalars(manager_clients_query(manager_name)).all())
