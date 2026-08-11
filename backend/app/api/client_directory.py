import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.entities import Client, ClientStatus, Phone
from app.services.client_directory import build_client_record, extract_directory_phones, normalize_directory_phone


router = APIRouter(prefix="/api", tags=["calltrack"])
logger = logging.getLogger(__name__)


def json_response(payload: dict, status_code: int = 200) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status_code=status_code,
        media_type="application/json; charset=utf-8",
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
    normalized = normalize_directory_phone(phone)
    if normalized is None:
        return json_response({"status": "error", "message": "Номер должен содержать не менее 10 цифр"}, 422)
    masked = f"******{normalized[-4:]}"
    logger.info("Запрос карточки клиента: телефон=%s", masked)
    try:
        clients = db.execute(
            select(Client)
            .join(Phone, Phone.client_id == Client.id)
            .where(Phone.phone.like(f"%{normalized}"))
            .options(joinedload(Client.phones), joinedload(Client.emails), joinedload(Client.trade_places))
            .order_by(Client.id)
        ).unique().scalars().all()
        records = []
        for client in clients:
            normalized_client_phones = extract_directory_phones([item.phone for item in client.phones])
            if normalized in normalized_client_phones:
                record = build_client_record(client, normalized_phones=False)
                if record:
                    records.append(record)
        logger.info("Карточка клиента: телефон=%s, проверено=%s, совпадений=%s", masked, len(clients), len(records))
        if not records:
            return json_response({
                "status": "success", "found": False, "data": [],
                "reason": "Клиент с указанным номером не найден",
            })
        return json_response({"status": "success", "found": True, "data": records})
    except Exception:
        logger.exception("Ошибка поиска карточки клиента: телефон=%s", masked)
        return json_response({"status": "error", "message": "Не удалось загрузить карточку клиента"}, 500)
