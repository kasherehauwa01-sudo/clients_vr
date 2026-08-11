import json
import logging
from time import monotonic

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.entities import Client, ClientStatus, Phone
from app.services.client_directory import build_client_record, extract_directory_phones, normalize_directory_phone


router = APIRouter(prefix="/api", tags=["calltrack"])
logger = logging.getLogger(__name__)


def json_response(payload: dict, status_code: int = 200, headers: dict[str, str] | None = None) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status_code=status_code,
        media_type="application/json; charset=utf-8",
        headers=headers,
    )


@router.get("/get_clients.php")
def get_clients_directory(db: Session = Depends(get_db)) -> Response:
    try:
        clients = db.execute(
            select(Client)
            .where(Client.status == ClientStatus.active, Client.name.is_not(None), Client.name != "")
            .options(joinedload(Client.phones), joinedload(Client.emails), joinedload(Client.trade_places))
            .order_by(Client.id)
        ).unique().scalars().all()
        data = [record for client in clients if (record := build_client_record(client, normalized_phones=True))]
        return json_response({"status": "success", "data": data, "total": len(data)})
    except Exception:
        logger.exception("Не удалось сформировать справочник клиентов для CallTrack")
        return json_response(
            {"status": "error", "message": "Не удалось загрузить справочник клиентов"},
            status_code=500,
        )


@router.get("/client_card.php")
def get_client_card(phone: str = "", db: Session = Depends(get_db)) -> Response:
    started_at = monotonic()
    normalized = normalize_directory_phone(phone)
    if normalized is None:
        total_ms = (monotonic() - started_at) * 1000
        return json_response(
            {"status": "error", "message": "Номер телефона должен содержать не менее 10 цифр"}, 422,
            {"Server-Timing": f"clients-total;dur={total_ms:.1f}"},
        )
    masked = f"******{normalized[-4:]}"
    # Импорт уже сохраняет российские телефоны в каноническом виде +7XXXXXXXXXX.
    # Несколько точных вариантов позволяют использовать существующий B-tree
    # ix_phones_phone и не требуют медленного LIKE либо новой миграции данных.
    indexed_phone_values = (f"+7{normalized}", f"7{normalized}", f"8{normalized}", normalized)
    normalized_at = monotonic()
    logger.info("Clients card: start phone=%s, normalization=%.1f ms", masked, (normalized_at - started_at) * 1000)
    try:
        query_started_at = monotonic()
        clients = db.execute(
            select(Client)
            .join(Phone, Phone.client_id == Client.id)
            .where(Phone.phone.in_(indexed_phone_values))
            .options(joinedload(Client.phones), joinedload(Client.emails), joinedload(Client.trade_places))
            .order_by(Client.id)
        ).unique().scalars().all()
        query_finished_at = monotonic()
        records = []
        for client in clients:
            normalized_client_phones = extract_directory_phones([item.phone for item in client.phones])
            if normalized in normalized_client_phones:
                record = build_client_record(client, normalized_phones=False)
                if record:
                    records.append(record)
        serialization_started_at = monotonic()
        payload = {
            "status": "success", "found": bool(records), "normalized_phone": normalized,
            "data": records, "total": len(records),
        }
        if not records:
            payload["reason"] = "Клиент с указанным номером не найден"
        query_ms = (query_finished_at - query_started_at) * 1000
        # Кодирование выполняется здесь, чтобы в Server-Timing вошла и сериализация.
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        finished_at = monotonic()
        serialization_ms = (finished_at - serialization_started_at) * 1000
        total_ms = (finished_at - started_at) * 1000
        logger.info(
            "Clients card: query=%.1f ms, serialization=%.1f ms, total=%.1f ms, matches=%s",
            query_ms, serialization_ms, total_ms, len(records),
        )
        return Response(
            content=body,
            media_type="application/json; charset=utf-8",
            headers={"Server-Timing": f"clients-db;dur={query_ms:.1f}, clients-total;dur={total_ms:.1f}"},
        )
    except Exception:
        logger.exception("Ошибка поиска карточки клиента: телефон=%s", masked)
        total_ms = (monotonic() - started_at) * 1000
        return json_response(
            {"status": "error", "message": "Не удалось загрузить карточку клиента"}, 500,
            {"Server-Timing": f"clients-total;dur={total_ms:.1f}"},
        )
