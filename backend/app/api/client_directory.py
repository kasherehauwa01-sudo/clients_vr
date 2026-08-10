import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.entities import Client, ClientStatus, Phone
from app.services.client_directory import build_client_directory


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
        rows = db.execute(
            select(Client.id, Client.name, Phone.phone)
            .join(Phone, Phone.client_id == Client.id)
            .where(Client.status == ClientStatus.active, Client.name.is_not(None), Client.name != "")
            .order_by(Client.id, Phone.id)
        ).all()
        data = build_client_directory(rows)
        return json_response({"status": "success", "data": data, "total": len(data)})
    except Exception:
        logger.exception("Не удалось сформировать справочник клиентов для CallTrack")
        return json_response(
            {"status": "error", "message": "Не удалось загрузить справочник клиентов"},
            status_code=500,
        )
