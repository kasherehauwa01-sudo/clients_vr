from io import BytesIO
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.orm import Session, selectinload
from starlette.concurrency import run_in_threadpool
import xlsxwriter
from app.db.session import SessionLocal, get_db
from app.models.entities import AuditLog, Client, ClientStatus, Email, Import, ImportIssue, Phone, TradePlace
from app.schemas.client import BulkUpdate, ClientDetail, ClientListItem, PagedClients
from app.services.importer import import_files

router = APIRouter(prefix="/api", tags=["clients"])

MANAGER_ORDER = [
    "Пашута М.С.", "Пашута М.С. (Ростов)", "Родина", "Родина Е.В. (Ростов)",
    "Новожилова М.", "Королева Светлана", "Ромащенко Екатерина", "Селянкина Татьяна",
    "Суркова Н.", "Трошина Лариса", "Шакулова Екатерина", "Антюфеева Яна",
    "Бабушкина Виктория", "Самойлова", "Андреева Дарья", "Гаина Татьяна",
    "Гордиенко", "Ермохина Ирина", "Кульченко Лилия", "Никишова Ольга",
    "Пименова Любовь", "Пирожкова Татьяна", "Стародубцева Полина", "Яицкая Ольга",
    "СОТРУДНИК АВИАТОРОВ", "СОТРУДНИК АХТУБИНСК", "СОТРУДНИК БАХТУРОВА",
    "СОТРУДНИК ЕВРОПА", "СОТРУДНИК ИДЕЯ", "СОТРУДНИК ПАРКХАУС",
    "СОТРУДНИК ПРИВОЗ", "СОТРУДНИК САНВЭЙ", "СОТРУДНИК СТРОЙГРАД",
    "СОТРУДНИК ТУЛАК", "СОТРУДНИК ЦИТРУС", "СОТРУДНИК ЦУМ",
    "Существующие сотрудники", "Клишко Ю.Н.", "МАРКЕТПЛЕЙСЫ", "Наш Китай",
    "Нет менеджера", "Дегтярев Алексей", "Дегтярева Оксана Александровна", "!!!", "<>",
]


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok"}


def to_list_item(client: Client, last_import_at=None) -> ClientListItem:
    emails = sorted({email.email.strip() for email in client.emails if email.email and email.email.strip()})
    return ClientListItem(
        id=client.id,
        name=client.name,
        company=client.company,
        manager=client.manager,
        phone="\n".join(sorted({phone.phone for phone in client.phones})) or None,
        email="\n".join(emails) or None,
        trade_place=client.trade_places[0].place if client.trade_places else None,
        birth_date=client.birth_date,
        last_import_at=last_import_at,
        status=client.status.value,
    )


def apply_client_filters(
    query,
    *,
    search=None,
    phone_search=None,
    manager=None,
    company=None,
    price_type=None,
    buyer_type=None,
    counterparty_type=None,
    trade_place=None,
    has_email=None,
    has_phone=None,
    status=None,
    birth_day=None,
    birth_month=None,
):
    if search:
        term = f"%{search.lower()}%"
        query = query.where(func.lower(Client.name).like(term))
    if phone_search:
        query = query.where(Client.phones.any(Phone.phone == phone_search.strip()))
    if manager:
        include_empty_manager = "Нет менеджера" in manager
        selected_managers = [value for value in manager if value != "Нет менеджера"]
        manager_conditions = []
        if selected_managers:
            manager_conditions.append(Client.manager.in_(selected_managers))
        if include_empty_manager:
            manager_conditions.append(or_(Client.manager.is_(None), Client.manager == ""))
        query = query.where(or_(*manager_conditions))
    if company:
        query = query.where(Client.company == company)
    if price_type:
        query = query.where(Client.price_type.in_(price_type))
    if buyer_type:
        query = query.where(Client.buyer_type.in_(buyer_type))
    if counterparty_type:
        query = query.where(Client.counterparty_type.in_(counterparty_type))
    if trade_place:
        query = query.where(Client.trade_places.any(TradePlace.place == trade_place))
    if has_email is not None:
        # Email.email — обязательное нормализованное поле, поэтому достаточно
        # проверить непустое значение. Функции trim/length внутри relationship.any
        # на рабочем PostgreSQL приводили к ошибке выполнения запроса.
        has_filled_email = Client.emails.any(Email.email != "")
        query = query.where(has_filled_email if has_email else ~has_filled_email)
    if has_phone is not None:
        query = query.where(Client.phones.any() if has_phone else ~Client.phones.any())
    if status:
        query = query.where(Client.status == status)
    if birth_day:
        query = query.where(func.extract("day", Client.birth_date) == birth_day)
    if birth_month:
        query = query.where(func.extract("month", Client.birth_date) == birth_month)
    return query


@router.get("/clients", response_model=PagedClients)
def clients(
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: str = "100",
    search: str | None = None,
    phone_search: str | None = None,
    manager: list[str] | None = Query(None),
    company: str | None = None,
    price_type: list[str] | None = Query(None),
    buyer_type: list[str] | None = Query(None),
    counterparty_type: list[str] | None = Query(None),
    trade_place: str | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    status: str | None = None,
    birth_day: int | None = None,
    birth_month: int | None = None,
    sort: str = "name",
    order: str = "asc",
):
    page = max(page, 1)
    show_all = page_size == "all"
    try:
        parsed_page_size = 100 if show_all else int(page_size)
    except ValueError:
        parsed_page_size = 100
    parsed_page_size = min(max(parsed_page_size, 1), 500)
    filtered_ids = apply_client_filters(
        select(Client.id),
        search=search,
        phone_search=phone_search,
        manager=manager,
        company=company,
        price_type=price_type,
        buyer_type=buyer_type,
        counterparty_type=counterparty_type,
        trade_place=trade_place,
        has_email=has_email,
        has_phone=has_phone,
        status=status,
        birth_day=birth_day,
        birth_month=birth_month,
    ).distinct().subquery()
    total = db.scalar(select(func.count()).select_from(filtered_ids)) or 0
    sort_map = {
        "name": Client.name,
        "company": Client.company,
        "manager": Client.manager,
        "birth_date": Client.birth_date,
        "updated_at": Client.updated_at,
        "last_import": Import.imported_at,
    }
    sort_column = sort_map.get(sort, Client.name)
    order_by = sort_column.desc().nullslast() if order == "desc" else sort_column.asc().nullslast()
    availability_order = case((Client.status == ClientStatus.out_of_stock, 1), else_=0)
    stmt = (
        select(Client, Import.imported_at)
        .join(filtered_ids, filtered_ids.c.id == Client.id)
        .outerjoin(Import, Client.last_import_id == Import.id)
        .options(selectinload(Client.phones), selectinload(Client.emails), selectinload(Client.trade_places))
        .order_by(availability_order.asc(), order_by, Client.id.asc())
    )
    if show_all:
        page = 1
        response_page_size = total
    else:
        stmt = stmt.offset((page - 1) * parsed_page_size).limit(parsed_page_size)
        response_page_size = parsed_page_size
    items = [to_list_item(client, imported_at) for client, imported_at in db.execute(stmt).all()]
    return PagedClients(items=items, total=total, page=page, page_size=response_page_size)


@router.get("/clients-filter-options")
def client_filter_options(db: Session = Depends(get_db)):
    managers_from_db = db.scalars(
        select(Client.manager).where(Client.manager.is_not(None), Client.manager != "").distinct().order_by(Client.manager)
    ).all()
    manager_rank = {manager: index for index, manager in enumerate(MANAGER_ORDER)}
    managers = sorted(
        set(managers_from_db) | {"Нет менеджера"},
        key=lambda manager: (manager_rank.get(manager, len(MANAGER_ORDER)), manager.casefold()),
    )
    price_types = db.scalars(
        select(Client.price_type).where(Client.price_type.is_not(None), Client.price_type != "").distinct().order_by(Client.price_type)
    ).all()
    buyer_types = db.scalars(
        select(Client.buyer_type).where(Client.buyer_type.is_not(None), Client.buyer_type != "").distinct().order_by(Client.buyer_type)
    ).all()
    counterparty_types = db.scalars(
        select(Client.counterparty_type)
        .where(Client.counterparty_type.is_not(None), Client.counterparty_type != "")
        .distinct()
        .order_by(Client.counterparty_type)
    ).all()
    return {
        "managers": managers,
        "price_types": price_types,
        "buyer_types": buyer_types,
        "counterparty_types": counterparty_types,
    }


@router.get("/clients/{client_id}", response_model=ClientDetail)
def client_detail(client_id: int, db: Session = Depends(get_db)):
    client = db.scalar(
        select(Client)
        .where(Client.id == client_id)
        .options(selectinload(Client.phones), selectinload(Client.emails), selectinload(Client.trade_places))
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    first_import = db.get(Import, client.first_import_id) if client.first_import_id else None
    last_import = db.get(Import, client.last_import_id) if client.last_import_id else None
    base = to_list_item(client, last_import.imported_at if last_import else None).model_dump()
    base.update(
        price_type=client.price_type,
        director=client.director,
        contact_person=client.contact_person,
        raw_common_phones=client.raw_common_phones,
        raw_sms_phones=client.raw_sms_phones,
        client_source=client.client_source,
        last_purchase_date=client.last_purchase_date,
        buyer_type=client.buyer_type,
        counterparty_type=client.counterparty_type,
        created_at=client.created_at,
        updated_at=client.updated_at,
        first_import_at=first_import.imported_at if first_import else None,
        last_import_file=last_import.file_name if last_import else None,
        phones=[{"phone": phone.phone, "type": phone.type.value} for phone in client.phones],
        emails=[email.email for email in client.emails],
        trade_places=[place.place for place in client.trade_places],
    )
    return ClientDetail(**base)


@router.post("/imports")
async def upload_import(files: list[UploadFile] = File(...)):
    payload = [(file.filename or "import.xlsx", await file.read()) for file in files]
    # Разбор больших XLS и запись тысяч клиентов — синхронная CPU/DB-работа.
    # Выполнение её в async endpoint блокировало event loop Uvicorn: nginx не
    # получал ответ и возвращал 504, а параллельно нельзя было открыть журнал.
    def run_import():
        with SessionLocal() as db:
            return import_files(db, payload)

    summary = await run_in_threadpool(run_import)
    return {"message": "Импорт завершен", **summary.model_dump()}


@router.get("/imports")
def imports(db: Session = Depends(get_db)):
    return db.scalars(select(Import).order_by(Import.imported_at.desc()).limit(200)).all()


@router.get("/imports/{import_id}/issues")
def import_issues(import_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(ImportIssue).where(ImportIssue.import_id == import_id).order_by(ImportIssue.id)).all()




@router.get("/logs")
def logs(db: Session = Depends(get_db)):
    imports = db.scalars(
        select(Import).where(~Import.log_hidden).order_by(Import.id.desc()).limit(100)
    ).all()
    import_ids = [item.id for item in imports]
    first_errors: dict[int, str] = {}
    if import_ids:
        errors = db.execute(
            select(ImportIssue.import_id, ImportIssue.message)
            .where(ImportIssue.import_id.in_(import_ids), ImportIssue.level == "error")
            .order_by(ImportIssue.id)
        ).all()
        for import_id, message in errors:
            first_errors.setdefault(import_id, message)
    return [
        {
            "id": f"import-{item.id}",
            "created_at": item.imported_at,
            "source": "Импорт",
            "level": "error" if item.error_count else "info",
            "process": item.file_name,
            "row_number": None,
            "message": (
                f"Найдено строк: {item.rows_count}. Загружено: {item.added_count}. "
                f"Обновлено: {item.updated_count}. Пропущено: {item.skipped_count}. Ошибок: {item.error_count}."
                + (f" Ошибка: {first_errors[item.id]}" if item.id in first_errors else "")
            ),
        }
        for item in imports
    ]


@router.delete("/logs")
def delete_logs(db: Session = Depends(get_db)):
    # Import нельзя удалять физически: на него ссылаются карточки клиентов.
    # Поэтому служебные записи скрываем, а собственно события удаляем полностью.
    hidden = db.execute(update(Import).where(~Import.log_hidden).values(log_hidden=True)).rowcount or 0
    db.execute(delete(ImportIssue))
    db.execute(delete(AuditLog))
    db.commit()
    return {"deleted": hidden}

@router.post("/clients/bulk")
def bulk_update(payload: BulkUpdate, db: Session = Depends(get_db)):
    clients_to_update = db.scalars(select(Client).where(Client.id.in_(payload.ids))).all()
    for client in clients_to_update:
        if payload.manager is not None:
            client.manager = payload.manager
        if payload.price_type is not None:
            client.price_type = payload.price_type
        if payload.status is not None:
            client.status = payload.status
        db.add(AuditLog(client_id=client.id, action="bulk_update", payload=payload.model_dump_json(exclude_none=True)))
    db.commit()
    return {"updated": len(clients_to_update)}


@router.delete("/clients")
def bulk_delete(
    ids: str | None = None,
    delete_all: bool = Query(False, alias="all"),
    db: Session = Depends(get_db),
):
    if delete_all:
        # Связанные телефоны, email и места торговли удаляются на уровне БД
        # благодаря внешним ключам с ON DELETE CASCADE.
        deleted = db.execute(delete(Client)).rowcount or 0
        db.add(AuditLog(action="delete_all_clients", payload=f"Удалено клиентов: {deleted}"))
        db.commit()
        return {"deleted": deleted}
    if not ids:
        raise HTTPException(status_code=400, detail="Не переданы строки для удаления")
    id_list = [int(value) for value in ids.split(",") if value.strip()]
    clients_to_delete = db.scalars(select(Client).where(Client.id.in_(id_list))).all()
    for client in clients_to_delete:
        db.delete(client)
    db.add(AuditLog(action="bulk_delete", payload=",".join(map(str, id_list))))
    db.commit()
    return {"deleted": len(clients_to_delete)}


@router.get("/clients-export.xlsx")
def export_clients(
    db: Session = Depends(get_db),
    search: str | None = None,
    phone_search: str | None = None,
    manager: list[str] | None = Query(None),
    company: str | None = None,
    price_type: list[str] | None = Query(None),
    buyer_type: list[str] | None = Query(None),
    counterparty_type: list[str] | None = Query(None),
    trade_place: str | None = None,
    has_email: bool | None = None,
    has_phone: bool | None = None,
    status: str | None = None,
    birth_day: int | None = None,
    birth_month: int | None = None,
):
    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet("clients")
    headers = [
        "Наименование", "Фирма", "Менеджер", "Телефон", "Email", "Место торговли",
        "Дата рождения", "Источник клиента", "Дата последней покупки", "Вид покупателя",
        "Вид контрагента", "Статус",
    ]
    for column, header in enumerate(headers):
        worksheet.write(0, column, header)
    filtered_ids = apply_client_filters(
        select(Client.id),
        search=search,
        phone_search=phone_search,
        manager=manager,
        company=company,
        price_type=price_type,
        buyer_type=buyer_type,
        counterparty_type=counterparty_type,
        trade_place=trade_place,
        has_email=has_email,
        has_phone=has_phone,
        status=status,
        birth_day=birth_day,
        birth_month=birth_month,
    ).distinct().subquery()
    stmt = (
        select(Client)
        .join(filtered_ids, filtered_ids.c.id == Client.id)
        .options(selectinload(Client.phones), selectinload(Client.emails), selectinload(Client.trade_places))
        .order_by(case((Client.status == ClientStatus.out_of_stock, 1), else_=0), Client.name, Client.id)
    )
    for row_number, client in enumerate(db.scalars(stmt), start=1):
        worksheet.write_row(
            row_number,
            0,
            [
                client.name,
                client.company or "",
                client.manager or "",
                "\n".join(sorted({phone.phone for phone in client.phones})),
                "\n".join(sorted({email.email.strip() for email in client.emails if email.email and email.email.strip()})),
                client.trade_places[0].place if client.trade_places else "",
                str(client.birth_date or ""),
                client.client_source or "",
                str(client.last_purchase_date or ""),
                client.buyer_type or "",
                client.counterparty_type or "",
                client.status.value,
            ],
        )
    workbook.close()
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=clients.xlsx"},
    )
