import json
import asyncio
from types import SimpleNamespace

from app.api.client_directory import get_client_card, get_clients_directory
from app.services.client_directory import build_client_directory, compact_fields, extract_directory_phones


class FakeResult:
    def __init__(self, rows): self.rows = rows
    def unique(self): return self
    def scalars(self): return self
    def all(self): return self.rows


class FakeSession:
    def __init__(self, rows=None, error: Exception | None = None):
        self.rows, self.error, self.statement, self.execute_count = rows or [], error, None, 0
    def execute(self, statement):
        self.statement = statement
        if self.error: raise self.error
        self.execute_count += 1
        return FakeResult(self.rows if self.execute_count == 1 else [])
    def expunge_all(self): pass


def client(client_id, name, phones, **values):
    defaults = dict(
        id=client_id, name=name, price_type=None, manager=None, birth_date=None,
        raw_common_phones=None, raw_sms_phones=None, director=None, company=None,
        raw_email=None, raw_email_source_known=False,
        contact_person=None, client_source=None, last_purchase_date=None,
        buyer_type=None, counterparty_type=None, status="active", created_at=None, updated_at=None, emails=[], trade_places=[],
    )
    defaults.update(values)
    defaults["phones"] = [SimpleNamespace(phone=value, type="common") for value in phones]
    return SimpleNamespace(**defaults)


def response_json(response):
    if hasattr(response, "body"):
        return json.loads(response.body.decode("utf-8"))

    async def consume_stream() -> bytes:
        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk.encode("utf-8") if isinstance(chunk, str) else chunk)
        return b"".join(chunks)

    return json.loads(asyncio.run(consume_stream()).decode("utf-8"))


def test_multiple_phones_are_normalized_in_existing_directory() -> None:
    data = build_client_directory([(1, "ООО Ромашка", "+7 (999) 123-45-67; 8 (495) 111-22-33")])
    assert data == [{"name": "ООО Ромашка", "phones": ["9991234567", "4951112233"]}]


def test_duplicate_phone_formats_are_removed() -> None:
    assert extract_directory_phones(["+7 (999) 123-45-67", "8 999 123 45 67"]) == ["9991234567"]


def test_card_matches_country_code_and_plain_phone() -> None:
    response = get_client_card(phone="+7 (999) 123-45-67", db=FakeSession([client(1, "ООО", ["9991234567"])]))
    assert response_json(response)["found"] is True


def test_card_matches_eight_prefix_to_plus_seven() -> None:
    response = get_client_card(phone="8 999 123 45 67", db=FakeSession([client(1, "ООО", ["+79991234567"])]))
    assert response_json(response)["data"][0]["name"] == "ООО"


def test_phone_in_array_and_among_multiple_values_is_found() -> None:
    item = client(1, "ООО", ["+74951112233", "+79991234567"])
    response = get_client_card(phone="9991234567", db=FakeSession([item]))
    assert response_json(response)["data"][0]["phones"] == ["+74951112233", "+79991234567"]


def test_card_query_uses_existing_indexed_phone_column() -> None:
    db = FakeSession()
    get_client_card(phone="+7 (999) 123-45-67", db=db)
    sql = str(db.statement)
    assert "phones.phone IN" in sql
    assert "LIKE" not in sql.upper()


def test_multiple_phones_in_one_string_become_array_items() -> None:
    item = client(1, "ООО", ["+7 (495) 111-22-33; +7 (999) 123-45-67"])
    phones = response_json(get_client_card(phone="9991234567", db=FakeSession([item])))["data"][0]["phones"]
    assert phones == ["+7 (495) 111-22-33", "+7 (999) 123-45-67"]


def test_all_filled_business_fields_returned_and_empty_excluded() -> None:
    item = client(1, "ООО", ["+79991234567"], company="Фирма", manager="Иван", director="", raw_email="mail@example.ru", raw_email_source_known=True, emails=[SimpleNamespace(email="from-other-field@example.ru")])
    fields = response_json(get_client_card(phone="9991234567", db=FakeSession([item])))["data"][0]["fields"]
    assert fields["Фирма"] == "Фирма"
    assert fields["Менеджер"] == "Иван"
    assert fields["Email"] == ["mail@example.ru"]
    assert "Руководитель" not in fields


def test_legacy_card_email_is_not_empty_before_reimport() -> None:
    item = client(1, "ООО", ["+79991234567"], emails=[SimpleNamespace(email="legacy@example.ru")])
    fields = response_json(get_client_card(phone="9991234567", db=FakeSession([item])))["data"][0]["fields"]
    assert fields["Email"] == ["legacy@example.ru"]


def test_secret_fields_are_excluded() -> None:
    assert compact_fields({"Наименование": "ООО", "Комментарий": "   ", "password": "secret", "api_key": "key"}) == {"Наименование": "ООО"}


def test_shared_phone_returns_all_clients() -> None:
    rows = [client(1, "Первый", ["+79991234567"]), client(2, "Второй", ["8 999 123-45-67"])]
    payload = response_json(get_client_card(phone="9991234567", db=FakeSession(rows)))
    assert [item["name"] for item in payload["data"]] == ["Первый", "Второй"]


def test_short_phone_returns_422() -> None:
    response = get_client_card(phone="12345", db=FakeSession())
    assert response.status_code == 422
    assert response_json(response) == {"status": "error", "message": "Номер телефона должен содержать не менее 10 цифр"}
    assert "clients-total" in response.headers["server-timing"]


def test_missing_phone_returns_found_false() -> None:
    response = get_client_card(phone="9991234567", db=FakeSession([client(1, "ООО", ["+74951112233"])]))
    assert response_json(response) == {
        "status": "success", "found": False, "normalized_phone": "9991234567",
        "data": [], "total": 0, "reason": "Клиент с указанным номером не найден",
    }
    assert "clients-db" in response.headers["server-timing"]


def test_existing_list_format_remains_compatible() -> None:
    db = FakeSession([client(1, "ООО", ["+79991234567"])])
    response = get_clients_directory(db=db)
    payload = response_json(response)
    assert response.status_code == 200
    assert payload["status"] == "success"
    assert payload["data"][0]["name"] == "ООО"
    assert payload["data"][0]["phones"] == ["9991234567"]
    assert payload["total"] == 1
    assert "LIMIT" in str(db.statement).upper()


def test_empty_directory_returns_http_200() -> None:
    response = get_clients_directory(db=FakeSession())
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json; charset=utf-8"
    assert response_json(response) == {"status": "success", "data": [], "total": 0}


def test_database_error_returns_safe_json() -> None:
    response = get_clients_directory(db=FakeSession(error=RuntimeError("postgresql://user:password@db/private")))
    assert response.status_code == 500
    assert response_json(response) == {"status": "error", "message": "Не удалось загрузить справочник клиентов"}
    assert "password" not in response.body.decode("utf-8")
    assert "Traceback" not in response.body.decode("utf-8")


def test_card_database_error_returns_safe_json() -> None:
    response = get_client_card(
        phone="9991234567",
        db=FakeSession(error=RuntimeError("postgresql://user:password@db/private")),
    )
    assert response.status_code == 500
    assert response_json(response) == {"status": "error", "message": "Не удалось загрузить карточку клиента"}
    assert "password" not in response.body.decode("utf-8")
    assert "Traceback" not in response.body.decode("utf-8")
    assert "clients-total" in response.headers["server-timing"]
