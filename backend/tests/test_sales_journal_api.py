from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
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
    # SQLite по умолчанию приводит регистр только для ASCII; тестовая функция
    # воспроизводит Unicode-поведение lower() рабочего PostgreSQL.
    event.listen(
        engine,
        "connect",
        lambda connection, _: connection.create_function(
            "lower", 1, lambda value: value.lower() if value is not None else None,
            deterministic=True,
        ),
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            [
                Client(name=" ООО Бета ", manager=" Иванов Иван ", buyer_type=" HoReCa ", status=ClientStatus.active),
                Client(name="ООО Альфа", manager="иванов иван", buyer_type="horeca", status=ClientStatus.active),
                Client(name="ооо альфа", manager="ИВАНОВ ИВАН", buyer_type="HORECA", status=ClientStatus.active),
                Client(name="ИП Смирнов", manager="Петров Пётр", buyer_type=" Розница ", status=ClientStatus.active),
                Client(name="Архив", manager="Архивный", buyer_type="Архивный тип", status=ClientStatus.archived),
                Client(name="Без менеджера", manager="   ", status=ClientStatus.active),
                Client(name="Пустой", manager=None, status=ClientStatus.active),
                Client(name="", manager="Менеджер без клиентов", status=ClientStatus.active),
                Client(name="   ", manager="Менеджер без клиентов", status=ClientStatus.active),
                Client(name="NULL-поля", manager=None, price_type=None, buyer_type=None, counterparty_type=None),
                Client(name="Пустые поля", manager=None, price_type="", buyer_type="", counterparty_type=""),
                Client(name="Пробельные поля", manager=None, price_type="   ", buyer_type="   ", counterparty_type="   "),
                Client(name="Заполненные поля", manager=None, price_type="Оптовая", buyer_type="Розница", counterparty_type="Юрлицо"),
                Client(name="Комбинация", manager=None, price_type=None, buyer_type="Розница", counterparty_type="Юрлицо"),
            ]
        )
        db.commit()

    def override_db() -> Generator[Session, None, None]:
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: Settings(integration_token="test-secret")
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


AUTH = {"Authorization": "Bearer test-secret"}


def test_integration_requires_shared_bearer_token(api: TestClient) -> None:
    assert api.get("/api/integration/buyer-types").status_code == 401
    assert api.get(
        "/api/integration/buyer-types",
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 401
    assert api.get("/api/integration/buyer-types", headers=AUTH).status_code == 200


def test_buyer_types_are_real_normalized_unique_values(api: TestClient) -> None:
    response = api.get("/api/integration/buyer-types", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == ["HoReCa", "Розница"]


def test_clients_can_be_filtered_by_buyer_type(api: TestClient) -> None:
    response = api.get(
        "/api/integration/clients",
        params={"buyer_type": "  HORECA  "},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert {item["name"] for item in response.json()} == {"ООО Альфа", "ооо альфа", " ООО Бета "}
    assert all("client" in item and "buyer_type" in item for item in response.json())
    assert api.get(
        "/api/integration/clients",
        params={"buyer_type": "Неизвестный"},
        headers=AUTH,
    ).json() == []


def test_manager_and_buyer_type_are_combined_with_and(api: TestClient) -> None:
    response = api.get(
        "/api/integration/clients",
        params={"manager": "Петров Пётр", "buyer_type": "HoReCa"},
        headers=AUTH,
    )

    assert response.json() == []


def test_unfiltered_integration_clients_remain_available(api: TestClient) -> None:
    response = api.get("/api/integration/clients", headers=AUTH)

    assert response.status_code == 200
    assert any(item["buyer_type"] is None for item in response.json())


def test_nested_buyer_type_endpoint_reuses_filter(api: TestClient) -> None:
    query_response = api.get(
        "/api/integration/clients", params={"buyer_type": "Розница"}, headers=AUTH
    )
    nested_response = api.get(
        "/api/integration/buyer-types/Розница/clients", headers=AUTH
    )

    assert nested_response.status_code == 200
    assert nested_response.json() == query_response.json()


def test_openapi_contains_buyer_type_contract(api: TestClient) -> None:
    schema = api.get("/openapi.json").json()
    operation = schema["paths"]["/api/integration/clients"]["get"]

    assert "buyer_type" in {parameter["name"] for parameter in operation["parameters"]}
    assert operation["security"] == [{"HTTPBearer": []}]


def registry_names(api: TestClient, **params: str) -> set[str]:
    response = api.get(
        "/api/clients",
        params={"page": "1", "page_size": "100", **params},
    )
    assert response.status_code == 200
    return {item["name"] for item in response.json()["items"]}


def test_empty_option_is_added_to_three_dynamic_filters(api: TestClient) -> None:
    response = api.get("/api/clients-filter-options")

    assert response.status_code == 200
    for key in ("price_types", "buyer_types", "counterparty_types"):
        assert response.json()[key][0] == "Не заполнено"
        assert response.json()[key].count("Не заполнено") == 1
        assert "" not in response.json()[key]
        assert "   " not in response.json()[key]


@pytest.mark.parametrize(
    "parameter",
    ["price_type", "buyer_type", "counterparty_type"],
)
def test_empty_filter_matches_null_empty_and_whitespace(
    api: TestClient,
    parameter: str,
) -> None:
    names = registry_names(api, **{parameter: "Не заполнено"})

    assert {"NULL-поля", "Пустые поля", "Пробельные поля"} <= names
    assert "Заполненные поля" not in names


def test_empty_filter_combines_with_filled_filter(api: TestClient) -> None:
    names = registry_names(
        api,
        price_type="Не заполнено",
        buyer_type="Розница",
    )

    assert {"ИП Смирнов", "Комбинация"} <= names
    assert "Заполненные поля" not in names


def test_empty_and_regular_values_in_one_filter_use_or(api: TestClient) -> None:
    response = api.get(
        "/api/clients",
        params=[
            ("page", "1"),
            ("page_size", "100"),
            ("price_type", "Не заполнено"),
            ("price_type", "Оптовая"),
        ],
    )

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["items"]}
    assert {"NULL-поля", "Пустые поля", "Пробельные поля", "Заполненные поля"} <= names
