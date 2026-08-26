from datetime import datetime
from types import SimpleNamespace

from app.api.client_directory import client_changes
from app.services.client_changes import payload_signature, record_change_if_needed, record_client_change


def make_client(client_id=1, name="ООО", phones=("+79991234567",), status="active"):
    return SimpleNamespace(
        id=client_id, name=name, status=status, company=None, manager=None,
        price_type=None, birth_date=None, director=None, contact_person=None,
        raw_common_phones=None, raw_sms_phones=None,
        raw_email=None,
        client_source=None, last_purchase_date=None, buyer_type=None,
        counterparty_type=None, updated_at=None,
        phones=[SimpleNamespace(phone=value) for value in phones],
        emails=[], trade_places=[],
    )


class AddSession:
    def __init__(self): self.added = []
    def add(self, value): self.added.append(value)


class ScalarResult:
    def __init__(self, values): self.values = values
    def all(self): return self.values


class ChangesSession:
    def __init__(self, values): self.values = values
    def scalars(self, statement): return ScalarResult(self.values)


def change(change_id, operation="delete", client_id=1, payload=None):
    return SimpleNamespace(
        id=change_id, changed_at=datetime(2026, 8, 13), operation=operation,
        client_id=client_id, payload=payload,
    )


def test_new_client_creates_upsert() -> None:
    db, client = AddSession(), make_client()
    assert record_change_if_needed(db, client, None) is True
    assert db.added[0].operation == "upsert"


def test_unchanged_import_does_not_create_event() -> None:
    db, client = AddSession(), make_client()
    assert record_change_if_needed(db, client, payload_signature(client)) is False
    assert db.added == []


def test_name_and_phone_changes_create_events() -> None:
    for mutate in (
        lambda item: setattr(item, "name", "Новое имя"),
        lambda item: item.phones.append(SimpleNamespace(phone="+74951112233")),
        lambda item: item.phones.pop(0),
    ):
        db, client = AddSession(), make_client()
        previous = payload_signature(client)
        mutate(client)
        assert record_change_if_needed(db, client, previous) is True


def test_deactivation_and_deletion_are_tombstones() -> None:
    db, client = AddSession(), make_client(status="archived")
    record_client_change(db, client)
    record_client_change(db, client, operation="delete")
    assert [item.operation for item in db.added] == ["delete", "delete"]
    assert all(item.payload is None for item in db.added)


def test_cursor_pagination_has_no_gaps_and_is_repeatable() -> None:
    values = [change(11), change(12), change(13)]
    first = client_changes(after_id=10, limit=2, db=ChangesSession(values))
    repeated = client_changes(after_id=10, limit=2, db=ChangesSession(values))
    second = client_changes(after_id=first["next_after_id"], limit=2, db=ChangesSession([values[2]]))
    assert [item["change_id"] for item in first["items"]] == [11, 12]
    assert repeated == first
    assert first["has_more"] is True
    assert [item["change_id"] for item in second["items"]] == [13]
    assert second["has_more"] is False


def test_same_timestamp_is_ordered_by_change_id() -> None:
    result = client_changes(after_id=0, limit=2, db=ChangesSession([change(1), change(2)]))
    assert [item["change_id"] for item in result["items"]] == [1, 2]


def test_upsert_page_contains_complete_snapshot() -> None:
    client = make_client()
    payload = payload_signature(client)
    result = client_changes(
        after_id=0, limit=500,
        db=ChangesSession([change(1, operation="upsert", payload=payload)]),
    )
    assert result["items"][0]["client"] == {
        "id": 1, "name": "ООО", "phones": ["+79991234567"], "status": "active",
    }
