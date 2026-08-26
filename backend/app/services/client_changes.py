import json
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.entities import Client, ClientChange, ClientStatus


def client_sync_payload(client: Client) -> dict:
    """Формирует устойчивый снимок только из бизнес-данных CallTrack."""
    def value(item):
        return item.isoformat() if isinstance(item, (date, datetime)) else item

    payload = {
        "id": client.id,
        "name": client.name,
        "phones": sorted({item.phone for item in client.phones if item.phone}),
        "company": client.company,
        "manager": client.manager,
        "emails": sorted({item.email for item in client.emails if item.email}),
        "trade_places": sorted({item.place for item in client.trade_places if item.place}),
        "status": getattr(client.status, "value", client.status),
        "price_type": client.price_type,
        "birth_date": value(client.birth_date),
        "director": client.director,
        "contact_person": client.contact_person,
        "raw_common_phones": client.raw_common_phones,
        "raw_sms_phones": client.raw_sms_phones,
        "raw_email": client.raw_email,
        "client_source": client.client_source,
        "last_purchase_date": value(client.last_purchase_date),
        "buyer_type": client.buyer_type,
        "counterparty_type": client.counterparty_type,
    }
    return {key: value(item) for key, item in payload.items() if item not in (None, "", [])}


def payload_signature(client: Client) -> str:
    return json.dumps(client_sync_payload(client), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def record_client_change(db: Session, client: Client, *, operation: str | None = None) -> ClientChange:
    actual_operation = operation or ("upsert" if client.status == ClientStatus.active else "delete")
    payload = payload_signature(client) if actual_operation == "upsert" else None
    change = ClientChange(client_id=client.id, operation=actual_operation, payload=payload)
    db.add(change)
    # onupdate не срабатывает при изменениях дочерних коллекций, поэтому дата
    # обновляется явно вместе с событием телефона/email/торговой точки.
    client.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    return change


def record_change_if_needed(db: Session, client: Client, previous_signature: str | None) -> bool:
    """Создаёт событие только при фактическом изменении снимка."""
    if previous_signature is not None and payload_signature(client) == previous_signature:
        return False
    record_client_change(db, client)
    return True
