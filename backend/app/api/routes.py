from io import BytesIO
import xlsxwriter
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from app.db.session import get_db
from app.models.entities import AuditLog, Client, Email, Import, ImportIssue, Phone, TradePlace
from app.schemas.client import BulkUpdate, ClientDetail, ClientListItem, PagedClients
from app.services.importer import import_files

router = APIRouter(prefix="/api")


def _item(c: Client) -> ClientListItem:
    return ClientListItem(id=c.id, name=c.name, company=c.company, manager=c.manager, phone=(c.phones[0].phone if c.phones else None), email=(c.emails[0].email if c.emails else None), trade_place=(c.trade_places[0].place if c.trade_places else None), birth_date=c.birth_date, last_import_at=getattr(c, "last_import_at", None), status=c.status.value)


@router.get("/clients", response_model=PagedClients)
def clients(db: Session = Depends(get_db), page: int = 1, page_size: int = 50, search: str | None = None, manager: str | None = None, company: str | None = None, price_type: str | None = None, trade_place: str | None = None, has_email: bool | None = None, has_phone: bool | None = None, status: str | None = None, birth_day: int | None = None, birth_month: int | None = None, sort: str = "name", order: str = "asc"):
    q = select(Client).options(selectinload(Client.phones), selectinload(Client.emails), selectinload(Client.trade_places)).outerjoin(Import, Client.last_import_id == Import.id).add_columns(Import.imported_at.label("last_import_at"))
    filters = []
    if search:
        term = f"%{search.lower()}%"; q = q.outerjoin(Email).outerjoin(Phone).outerjoin(TradePlace); filters.append(or_(func.lower(Client.name).like(term), func.lower(Client.company).like(term), func.lower(Client.contact_person).like(term), func.lower(Client.director).like(term), func.lower(Email.email).like(term), Phone.phone.like(term), func.lower(TradePlace.place).like(term)))
    if manager: filters.append(Client.manager == manager)
    if company: filters.append(Client.company == company)
    if price_type: filters.append(Client.price_type == price_type)
    if status: filters.append(Client.status == status)
    if birth_day: filters.append(func.extract("day", Client.birth_date) == birth_day)
    if birth_month: filters.append(func.extract("month", Client.birth_date) == birth_month)
    if has_email is True: filters.append(Client.emails.any())
    if has_email is False: filters.append(~Client.emails.any())
    if has_phone is True: filters.append(Client.phones.any())
    if has_phone is False: filters.append(~Client.phones.any())
    if trade_place: filters.append(Client.trade_places.any(TradePlace.place == trade_place))
    base = select(func.count(func.distinct(Client.id))).select_from(Client)
    for f in filters: q = q.where(f); base = base.where(f)
    sort_map = {"name": Client.name, "company": Client.company, "manager": Client.manager, "birth_date": Client.birth_date, "updated_at": Client.updated_at, "last_import": Import.imported_at}
    q = q.order_by((sort_map.get(sort) or Client.name).desc() if order == "desc" else (sort_map.get(sort) or Client.name).asc()).offset((page - 1) * page_size).limit(page_size).distinct()
    rows = db.execute(q).all(); items = []
    for c, imported_at in rows:
        c.last_import_at = imported_at; items.append(_item(c))
    return PagedClients(items=items, total=db.scalar(base) or 0, page=page, page_size=page_size)


@router.get("/clients/{client_id}", response_model=ClientDetail)
def client_detail(client_id: int, db: Session = Depends(get_db)):
    c = db.scalar(select(Client).where(Client.id == client_id).options(selectinload(Client.phones), selectinload(Client.emails), selectinload(Client.trade_places)))
    first = db.get(Import, c.first_import_id) if c and c.first_import_id else None; last = db.get(Import, c.last_import_id) if c and c.last_import_id else None
    item = _item(c).model_dump(); item.update(price_type=c.price_type, director=c.director, contact_person=c.contact_person, created_at=c.created_at, updated_at=c.updated_at, first_import_at=first.imported_at if first else None, last_import_file=last.file_name if last else None, phones=[{"phone": p.phone, "type": p.type.value} for p in c.phones], emails=[e.email for e in c.emails], trade_places=[p.place for p in c.trade_places])
    return ClientDetail(**item)


@router.post("/imports")
async def upload_import(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    payload = [(f.filename, await f.read()) for f in files]
    summary = import_files(db, payload)
    return {"message": "Импорт завершен", **summary.__dict__}


@router.get("/imports")
def imports(db: Session = Depends(get_db)):
    return db.scalars(select(Import).order_by(Import.imported_at.desc()).limit(200)).all()


@router.get("/imports/{import_id}/issues")
def import_issues(import_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(ImportIssue).where(ImportIssue.import_id == import_id)).all()


@router.post("/clients/bulk")
def bulk_update(payload: BulkUpdate, db: Session = Depends(get_db)):
    clients = db.scalars(select(Client).where(Client.id.in_(payload.ids))).all()
    for c in clients:
        if payload.manager is not None: c.manager = payload.manager
        if payload.price_type is not None: c.price_type = payload.price_type
        if payload.status is not None: c.status = payload.status
        db.add(AuditLog(client_id=c.id, action="bulk_update", payload=payload.model_dump_json()))
    db.commit(); return {"updated": len(clients)}


@router.delete("/clients")
def bulk_delete(ids: str, db: Session = Depends(get_db)):
    id_list = [int(x) for x in ids.split(",") if x]
    count = len(db.scalars(select(Client).where(Client.id.in_(id_list))).all())
    db.query(Client).filter(Client.id.in_(id_list)).delete(synchronize_session=False); db.commit(); return {"deleted": count}


@router.get("/clients-export.xlsx")
def export_clients(db: Session = Depends(get_db)):
    out = BytesIO(); wb = xlsxwriter.Workbook(out); ws = wb.add_worksheet("clients")
    headers = ["Наименование", "Фирма", "Менеджер", "Телефон", "Email", "Место торговли", "Дата рождения", "Статус"]
    for col, h in enumerate(headers): ws.write(0, col, h)
    for row, c in enumerate(db.scalars(select(Client).options(selectinload(Client.phones), selectinload(Client.emails), selectinload(Client.trade_places))).all(), 1):
        ws.write_row(row, 0, [c.name, c.company, c.manager, c.phones[0].phone if c.phones else "", c.emails[0].email if c.emails else "", c.trade_places[0].place if c.trade_places else "", str(c.birth_date or ""), c.status.value])
    wb.close(); out.seek(0)
    return StreamingResponse(out, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition":"attachment; filename=clients.xlsx"})
