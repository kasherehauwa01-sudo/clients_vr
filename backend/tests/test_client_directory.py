import json

from app.api.client_directory import get_clients_directory
from app.services.client_directory import build_client_directory, extract_directory_phones


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def all(self):
        return self.rows


class FakeSession:
    def __init__(self, rows=None, error: Exception | None = None):
        self.rows = rows or []
        self.error = error

    def execute(self, statement):
        if self.error:
            raise self.error
        return FakeResult(self.rows)


def response_json(response):
    return json.loads(response.body.decode("utf-8"))


def test_multiple_phones_are_normalized() -> None:
    data = build_client_directory([
        (1, "ООО Ромашка", "+7 (999) 123-45-67; 8 (495) 111-22-33"),
    ])

    assert data == [{"name": "ООО Ромашка", "phones": ["9991234567", "4951112233"]}]


def test_duplicate_phone_formats_are_removed() -> None:
    phones = extract_directory_phones(["+7 (999) 123-45-67", "8 999 123 45 67"])

    assert phones == ["9991234567"]


def test_client_without_name_is_skipped() -> None:
    assert build_client_directory([(1, "", "+7 999 123-45-67")]) == []


def test_client_without_valid_phone_is_skipped() -> None:
    assert build_client_directory([(1, "ООО Ромашка", "12345")]) == []


def test_empty_directory_returns_http_200() -> None:
    response = get_clients_directory(db=FakeSession())

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response_json(response) == {"status": "success", "data": [], "total": 0}


def test_database_error_returns_safe_json() -> None:
    response = get_clients_directory(db=FakeSession(error=RuntimeError("postgresql://user:password@db/private")))
    payload = response_json(response)

    assert response.status_code == 500
    assert payload == {"status": "error", "message": "Не удалось загрузить справочник клиентов"}
    assert "password" not in response.body.decode("utf-8")
    assert "Traceback" not in response.body.decode("utf-8")
