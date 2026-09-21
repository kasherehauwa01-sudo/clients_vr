from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models.entities import Client, ClientStatus


@pytest.fixture
def api() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                Client(name=" ООО Бета ", manager=" Иванов Иван ", status=ClientStatus.active),
                Client(name="ООО Альфа", manager="иванов иван", status=ClientStatus.active),
                Client(name="ооо альфа", manager="ИВАНОВ ИВАН", status=ClientStatus.active),
                Client(name="ИП Смирнов", manager="Петров Пётр", status=ClientStatus.active),
                Client(name="Архив", manager="Архивный", status=ClientStatus.archived),
                Client(name="Без менеджера", manager="   ", status=ClientStatus.active),
                Client(name="Пустой", manager=None, status=ClientStatus.active),
                Client(name="", manager="Менеджер без клиентов", status=ClientStatus.active),
                Client(name="   ", manager="Менеджер без клиентов", status=ClientStatus.active),
            ]
        )
        db.commit()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    engine.dispose()


def test_managers_are_trimmed_unique_sorted_and_active(api: TestClient) -> None:
    response = api.get("/api/managers")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == ["Иванов Иван", "Менеджер без клиентов", "Петров Пётр"]
    assert all(isinstance(value, str) for value in response.json())


def test_clients_match_exact_manager_case_insensitively(api: TestClient) -> None:
    response = api.get("/api/clients", params={"manager": "  ИВАНОВ ИВАН  "})

    assert response.status_code == 200
    assert response.json() == ["ООО Альфа", "ООО Бета"]
    assert api.get("/api/clients", params={"manager": "Иванов"}).json() == []


def test_manager_without_named_clients_returns_empty_array(api: TestClient) -> None:
    response = api.get("/api/clients", params={"manager": "менеджер без клиентов"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("params", [None, {"manager": ""}, {"manager": "   "}])
def test_manager_is_required(api: TestClient, params: dict[str, str] | None) -> None:
    response = api.get("/api/clients", params=params)

    assert response.status_code == 422
    assert "manager" in response.json()["detail"]


def test_registry_contract_remains_available_with_pagination(api: TestClient) -> None:
    response = api.get("/api/clients", params={"page": 1, "page_size": 10})

    assert response.status_code == 200
    assert isinstance(response.json(), dict)
    assert "items" in response.json()
