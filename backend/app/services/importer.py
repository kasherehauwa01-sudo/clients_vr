from dataclasses import dataclass
from io import BytesIO
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from openpyxl import load_workbook
import xlrd
from app.models.entities import AuditLog, Client, Email, Import, ImportIssue, Phone, PhoneType, TradePlace
from app.services.normalization import clean_text, normalize_email, normalize_phone, parse_date, split_values

HEADERS = {
    "Наименование": "name", "Тип цены": "price_type", "Менеджер": "manager", "Дата рождения": "birth_date",
    "Email": "emails", "Телефоны прочие": "common_phones", "Места торговли": "trade_places",
    "Телефоны для СМС и рассылки": "sms_phones", "Руководитель": "director", "Контактное лицо": "contact_person", "Фирма": "company",
}

@dataclass
class ImportSummary:
    files: int = 0; rows: int = 0; added: int = 0; updated: int = 0; skipped: int = 0; errors: int = 0; duplicates: int = 0


def _read_rows(filename: str, content: bytes) -> list[dict[str, object]]:
    if filename.lower().endswith(".xlsx"):
        ws = load_workbook(BytesIO(content), read_only=True, data_only=True).active
        rows = list(ws.iter_rows(values_only=True))
    elif filename.lower().endswith(".xls"):
        book = xlrd.open_workbook(file_contents=content)
        sh = book.sheet_by_index(0)
        rows = [[sh.cell_value(r, c) for c in range(sh.ncols)] for r in range(sh.nrows)]
    else:
        raise ValueError("Поддерживаются только .xls и .xlsx")
    if not rows:
        return []
    header = [clean_text(v) for v in rows[0]]
    mapped = {idx: HEADERS[h] for idx, h in enumerate(header) if h in HEADERS}
    return [{field: row[idx] if idx < len(row) else None for idx, field in mapped.items()} for row in rows[1:] if any(clean_text(v) for v in row)]


def _find_client(db: Session, row: dict, sms: list[str], phones: list[str], emails: list[str]) -> tuple[Client | None, bool]:
    for phone_set, type_filter in ((sms, PhoneType.sms), (phones + sms, None)):
        if phone_set:
            q = select(Client).join(Phone).where(Phone.phone.in_(phone_set))
            if type_filter: q = q.where(Phone.type == type_filter)
            found = db.scalars(q).unique().all()
            if found: return found[0], len(found) > 1
    if emails:
        found = db.scalars(select(Client).join(Email).where(Email.email.in_(emails))).unique().all()
        if found: return found[0], len(found) > 1
    name, company = clean_text(row.get("name")), clean_text(row.get("company"))
    if name and company:
        found = db.scalars(select(Client).where(Client.name == name, Client.company == company)).all()
        if found: return found[0], len(found) > 1
    return None, False


def _sync_children(client: Client, emails: list[str], sms: list[str], common: list[str], places: list[str]) -> None:
    existing_emails = {e.email for e in client.emails}
    for email in emails:
        if email not in existing_emails: client.emails.append(Email(email=email))
    existing_phones = {(p.phone, p.type) for p in client.phones}
    for phone, typ in [(p, PhoneType.sms) for p in sms] + [(p, PhoneType.common) for p in common]:
        if (phone, typ) not in existing_phones: client.phones.append(Phone(phone=phone, type=typ))
    existing_places = {p.place for p in client.trade_places}
    for place in places:
        if place not in existing_places: client.trade_places.append(TradePlace(place=place))


def import_files(db: Session, files: list[tuple[str, bytes]]) -> ImportSummary:
    total = ImportSummary(files=len(files))
    for filename, content in files:
        imp = Import(file_name=filename); db.add(imp); db.flush()
        try:
            rows = _read_rows(filename, content); imp.rows_count = len(rows); total.rows += len(rows)
            for num, row in enumerate(rows, start=2):
                try:
                    emails = [e for e in (normalize_email(v) for v in split_values(row.get("emails"))) if e]
                    sms = [p for p in (normalize_phone(v) for v in split_values(row.get("sms_phones"))) if p]
                    common = [p for p in (normalize_phone(v) for v in split_values(row.get("common_phones"))) if p]
                    places = [clean_text(v) for v in split_values(row.get("trade_places")) if clean_text(v)]
                    name = clean_text(row.get("name"))
                    if not name: imp.skipped_count += 1; total.skipped += 1; continue
                    client, duplicate = _find_client(db, row, sms, common, emails)
                    if duplicate:
                        total.duplicates += 1; db.add(ImportIssue(import_id=imp.id, row_number=num, level="warning", message="Найдено несколько совпадений клиента"))
                    data = dict(name=name, company=clean_text(row.get("company")), price_type=clean_text(row.get("price_type")), manager=clean_text(row.get("manager")), birth_date=parse_date(row.get("birth_date")), director=clean_text(row.get("director")), contact_person=clean_text(row.get("contact_person")), last_import_id=imp.id)
                    if client:
                        for k, v in data.items(): setattr(client, k, v)
                        imp.updated_count += 1; total.updated += 1; action = "client_updated"
                    else:
                        client = Client(**data, first_import_id=imp.id); db.add(client); imp.added_count += 1; total.added += 1; action = "client_created"
                    _sync_children(client, emails, sms, common, places)
                    db.flush(); db.add(AuditLog(client_id=client.id, action=action, payload=filename))
                except Exception as exc:
                    imp.error_count += 1; total.errors += 1; db.add(ImportIssue(import_id=imp.id, row_number=num, level="error", message=str(exc)))
        except Exception as exc:
            imp.error_count += 1; total.errors += 1; db.add(ImportIssue(import_id=imp.id, level="error", message=str(exc)))
        db.commit()
    return total
