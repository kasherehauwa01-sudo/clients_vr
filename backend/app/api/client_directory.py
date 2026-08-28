import json
import logging
from pathlib import Path
from time import monotonic
from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.session import get_db
from app.models.entities import Client, ClientChange, ClientStatus, Phone
from app.services.client_directory import build_client_record, extract_directory_phones, normalize_directory_phone


router = APIRouter(prefix="/api", tags=["calltrack"])
logger = logging.getLogger(__name__)
DIRECTORY_BATCH_SIZE = 250


def _resident_memory_bytes() -> int:
    """Возвращает текущий RSS процесса без дополнительных зависимостей."""
    try:
        for line in Path("/proc/self/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def _directory_batch(db: Session, after_id: int) -> tuple[list[Client], float]:
    started_at = monotonic()
    clients = db.execute(
        select(Client)
        .where(
            Client.id > after_id,
            Client.status == ClientStatus.active,
            Client.name.is_not(None),
            Client.name != "",
            Client.phones.any(),
        )
        # selectinload исключает декартово произведение phones × emails × places,
        # а ограниченный batch не удерживает весь справочник в памяти.
        .options(selectinload(Client.phones), selectinload(Client.emails), selectinload(Client.trade_places))
        .order_by(Client.id)
        .limit(DIRECTORY_BATCH_SIZE)
    ).scalars().all()
    return clients, monotonic() - started_at


def json_response(payload: dict, status_code: int = 200, headers: dict[str, str] | None = None) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status_code=status_code,
        media_type="application/json; charset=utf-8",
        headers=headers,
    )


@router.get("/get_clients.php")
def get_clients_directory(db: Session = Depends(get_db)) -> Response:
    started_at = monotonic()
    memory_before = _resident_memory_bytes()
    try:
        first_batch, first_sql_seconds = _directory_batch(db, 0)
    except Exception:
        logger.exception("Не удалось сформировать справочник клиентов для CallTrack")
        return json_response(
            {"status": "error", "message": "Не удалось загрузить справочник клиентов"},
            status_code=500,
        )

    def stream_directory() -> Iterator[bytes]:
        batch = first_batch
        sql_seconds = first_sql_seconds
        clients_count = 0
        json_bytes = 0
        formation_seconds = 0.0
        last_id = 0
        first_record = True
        prefix = b'{"status":"success","data":['
        json_bytes += len(prefix)
        yield prefix
        try:
            while batch:
                last_id = batch[-1].id
                batch_is_last = len(batch) < DIRECTORY_BATCH_SIZE
                for client in batch:
                    formation_started_at = monotonic()
                    record = build_client_record(client, normalized_phones=True)
                    if not record:
                        formation_seconds += monotonic() - formation_started_at
                        continue
                    encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
                    chunk = encoded if first_record else b"," + encoded
                    first_record = False
                    clients_count += 1
                    json_bytes += len(chunk)
                    formation_seconds += monotonic() - formation_started_at
                    yield chunk
                # Объекты предыдущей порции больше не нужны. Это удерживает RSS
                # примерно на уровне одного batch даже для большого справочника.
                db.expunge_all()
                if batch_is_last:
                    batch = []
                else:
                    batch, batch_sql_seconds = _directory_batch(db, last_id)
                    sql_seconds += batch_sql_seconds
            suffix = f'],"total":{clients_count}}}'.encode("utf-8")
            json_bytes += len(suffix)
            yield suffix
        finally:
            elapsed = monotonic() - started_at
            memory_after = _resident_memory_bytes()
            logger.info(
                "Clients directory: clients=%s, sql=%.3f s, build=%.3f s, total=%.3f s, json=%s bytes, rss_before=%s, rss_after=%s",
                clients_count, sql_seconds, formation_seconds, elapsed, json_bytes, memory_before, memory_after,
            )

    logger.info(
        "Clients directory: start, batch_size=%s, first_batch=%s, rss_before=%s",
        DIRECTORY_BATCH_SIZE, len(first_batch), memory_before,
    )
    return StreamingResponse(stream_directory(), media_type="application/json; charset=utf-8")


@router.get("/clients/changes/state")
def client_changes_state(db: Session = Depends(get_db)) -> dict:
    """Возвращает cursor, с которого можно начать delta после полного refresh."""
    last_change_id = db.scalar(select(ClientChange.id).order_by(ClientChange.id.desc()).limit(1)) or 0
    return {"status": "success", "last_change_id": last_change_id}


@router.get("/clients/changes")
def client_changes(
    after_id: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    db: Session = Depends(get_db),
) -> dict:
    """Выдаёт строго упорядоченную страницу идемпотентных изменений."""
    changes = db.scalars(
        select(ClientChange)
        .where(ClientChange.id > after_id)
        .order_by(ClientChange.id)
        .limit(limit + 1)
    ).all()
    has_more = len(changes) > limit
    page = changes[:limit]
    items = []
    for change in page:
        item = {
            "change_id": change.id,
            "changed_at": change.changed_at,
            "operation": change.operation,
            "client_id": change.client_id,
        }
        if change.operation == "upsert" and change.payload:
            item["client"] = json.loads(change.payload)
        items.append(item)
    return {
        "status": "success",
        "items": items,
        "next_after_id": page[-1].id if page else after_id,
        "has_more": has_more,
    }


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
