import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.entities import Client, ClientStatus
from app.schemas.integration import IntegrationClientOut

router = APIRouter(prefix="/api", tags=["sales-journal"])
bearer_scheme = HTTPBearer(auto_error=False)


def require_integration_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> None:
    """Проверяет единый Bearer-токен Integration API без его журналирования."""
    expected_token = settings.integration_token
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not credentials.credentials
        or not expected_token
        or not secrets.compare_digest(credentials.credentials, expected_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный или отсутствующий токен Integration API",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Одна dependency применяется ко всем текущим и будущим Integration endpoints.
integration_router = APIRouter(
    prefix="/api/integration",
    tags=["integration"],
    dependencies=[Depends(require_integration_token)],
)


def _normalized(column):
    return func.trim(column)


def _non_empty(column):
    return column.is_not(None), func.length(_normalized(column)) > 0


def _distinct_values_query(column):
    normalized = _normalized(column)
    return (
        select(func.min(normalized))
        .where(Client.status != ClientStatus.archived, *_non_empty(column))
        .group_by(func.lower(normalized))
        .order_by(func.lower(func.min(normalized)), func.min(normalized))
    )


def managers_query():
    return _distinct_values_query(Client.manager)


def buyer_types_query():
    return _distinct_values_query(Client.buyer_type)


def manager_clients_query(manager_name: str):
    client_name = _normalized(Client.name)
    return (
        select(func.min(client_name))
        .where(
            Client.status != ClientStatus.archived,
            *_non_empty(Client.name),
            func.lower(_normalized(Client.manager)) == manager_name.strip().lower(),
        )
        .group_by(func.lower(client_name))
        .order_by(func.lower(func.min(client_name)), func.min(client_name))
    )


def buyer_type_client_names_query(buyer_type: str):
    """Возвращает уникальные имена клиентов указанного вида покупателя."""
    client_name = _normalized(Client.name)
    expected = buyer_type.strip().casefold()

    if expected == "нет":
        buyer_type_condition = or_(
            Client.buyer_type.is_(None),
            func.length(_normalized(Client.buyer_type)) == 0,
        )
    else:
        buyer_type_condition = (
            func.lower(_normalized(Client.buyer_type)) == expected
        )

    return (
        select(func.min(client_name))
        .where(
            Client.status != ClientStatus.archived,
            *_non_empty(Client.name),
            buyer_type_condition,
        )
        .group_by(func.lower(client_name))
        .order_by(func.lower(func.min(client_name)), func.min(client_name))
    )


def integration_clients_query(*, manager: str | None = None, buyer_type: str | None = None):
    """Строит единый запрос клиентов; все фильтры объединяются через AND."""
    query = (
        select(Client)
        .where(Client.status != ClientStatus.archived, *_non_empty(Client.name))
        .order_by(func.lower(_normalized(Client.name)), Client.id)
    )
    if manager and manager.strip():
        query = query.where(
            func.lower(_normalized(Client.manager)) == manager.strip().lower()
        )
    if buyer_type and buyer_type.strip():
        query = query.where(
            func.lower(_normalized(Client.buyer_type)) == buyer_type.strip().lower()
        )
    return query


def load_integration_clients(
    db: Session,
    *,
    manager: str | None = None,
    buyer_type: str | None = None,
) -> list[IntegrationClientOut]:
    clients = db.scalars(
        integration_clients_query(manager=manager, buyer_type=buyer_type)
    ).all()
    return [IntegrationClientOut.model_validate(client) for client in clients]


@router.get("/managers", response_model=list[str])
def sales_journal_managers(db: Session = Depends(get_db)) -> list[str]:
    """Публичный совместимый endpoint из первоначальной интеграции."""
    return list(db.scalars(managers_query()).all())


def sales_journal_clients(manager_name: str, db: Session) -> list[str]:
    """Совместимая выдача только имён клиентов для `/api/clients`."""
    return list(db.scalars(manager_clients_query(manager_name)).all())


@integration_router.get("/managers", response_model=list[str])
def integration_managers(db: Session = Depends(get_db)) -> list[str]:
    return list(db.scalars(managers_query()).all())


@integration_router.get("/buyer-types", response_model=list[str])
def integration_buyer_types(db: Session = Depends(get_db)) -> list[str]:
    return list(db.scalars(buyer_types_query()).all())


@integration_router.get("/clients", response_model=list[IntegrationClientOut])
def integration_clients(
    manager: str | None = Query(default=None),
    manager_name: str | None = Query(default=None),
    buyer_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[IntegrationClientOut]:
    # manager_name поддерживается как совместимый псевдоним manager.
    selected_manager = manager if manager is not None else manager_name
    return load_integration_clients(
        db,
        manager=selected_manager,
        buyer_type=buyer_type,
    )


@integration_router.get(
    "/buyer-types/{buyer_type}/client-names",
    response_model=list[str],
)
def integration_client_names_by_buyer_type(
    buyer_type: str,
    db: Session = Depends(get_db),
) -> list[str]:
    """Уникальные имена клиентов выбранного вида покупателя для Sales Journal."""
    return list(db.scalars(buyer_type_client_names_query(buyer_type)).all())


@integration_router.get(
    "/buyer-types/{buyer_type}/clients",
    response_model=list[IntegrationClientOut],
)
def integration_clients_by_buyer_type(
    buyer_type: str,
    db: Session = Depends(get_db),
) -> list[IntegrationClientOut]:
    return load_integration_clients(db, buyer_type=buyer_type)
