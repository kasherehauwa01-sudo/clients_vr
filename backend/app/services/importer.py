from io import BytesIO
import re
import xlrd
from openpyxl import load_workbook
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.entities import AuditLog, Client, Email, Import, ImportIssue, Phone, PhoneType, TradePlace
from app.services.normalization import clean_text, normalize_email, normalize_phone, parse_date, split_values

COLUMN_ORDER = [
    "name",
    "price_type",
    "manager",
    "birth_date",
    "emails",
    "common_phones",
    "trade_places",
    "sms_phones",
    "director",
    "contact_person",
    "company",
]

HEADER_ALIASES = {
    "наименование": "name",
    "название": "name",
    "клиент": "name",
    "типцены": "price_type",
    "ценатип": "price_type",
    "менеджер": "manager",
    "датарождения": "birth_date",
    "др": "birth_date",
    "email": "emails",
    "emails": "emails",
    "почта": "emails",
    "телефоныпрочие": "common_phones",
    "прочиетелефоны": "common_phones",
    "телефон": "common_phones",
    "телефоны": "common_phones",
    "местаторговли": "trade_places",
    "местоторговли": "trade_places",
    "адрес": "trade_places",
    "телефоныдлясмсирассылки": "sms_phones",
    "телефондлясмсирассылки": "sms_phones",
    "телефоныдлярассылки": "sms_phones",
    "телефонсмс": "sms_phones",
    "руководитель": "director",
    "контактноелицо": "contact_person",
    "контакт": "contact_person",
    "фирма": "company",
    "компания": "company",
}


class ImportSummary(BaseModel):
    files: int = 0
    rows: int = 0
    added: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    duplicates: int = 0


def _normalize_header(value: object) -> str:
    text = clean_text(value) or ""
    return re.sub(r"[^0-9a-zа-яё]+", "", text.lower())


def _row_has_data(row: list[object]) -> bool:
    return any(clean_text(value) for value in row)


def _map_by_positions(row: list[object]) -> dict[str, object]:
    return {field: row[index] if index < len(row) else None for index, field in enumerate(COLUMN_ORDER)}


def _detect_header(rows: list[list[object]]) -> tuple[int | None, dict[int, str]]:
    best_index: int | None = None
    best_mapping: dict[int, str] = {}
    for index, row in enumerate(rows[:10]):
        mapping = {column_index: HEADER_ALIASES[key] for column_index, value in enumerate(row) if (key := _normalize_header(value)) in HEADER_ALIASES}
        if len(mapping) > len(best_mapping):
            best_index, best_mapping = index, mapping
    return (best_index, best_mapping) if len(best_mapping) >= 2 else (None, {})


def _rows_from_xlsx(content: bytes) -> list[list[object]]:
    ws = load_workbook(BytesIO(content), read_only=True, data_only=True).active
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _rows_from_xls(content: bytes) -> list[list[object]]:
    book = xlrd.open_workbook(file_contents=content)
    sheet = book.sheet_by_index(0)
    rows: list[list[object]] = []
    for row_index in range(sheet.nrows):
        values: list[object] = []
        for column_index in range(sheet.ncols):
            cell = sheet.cell(row_index, column_index)
            if cell.ctype == xlrd.XL_CELL_DATE:
                try:
                    values.append(xlrd.xldate.xldate_as_datetime(cell.value, book.datemode))
                except Exception:
                    values.append(cell.value)
            else:
                values.append(cell.value)
        rows.append(values)
    return rows


def _read_rows(filename: str, content: bytes) -> list[dict[str, object]]:
    lower_name = filename.lower()
    if lower_name.endswith(".xlsx"):
        raw_rows = _rows_from_xlsx(content)
    elif lower_name.endswith(".xls"):
        raw_rows = _rows_from_xls(content)
    else:
        raise ValueError("Поддерживаются только .xls и .xlsx")
    raw_rows = [row for row in raw_rows if _row_has_data(row)]
    if not raw_rows:
        return []
    header_index, mapping = _detect_header(raw_rows)
    data_rows = raw_rows[header_index + 1 :] if header_index is not None else raw_rows
    result: list[dict[str, object]] = []
    for offset, row in enumerate(data_rows, start=(header_index + 2 if header_index is not None else 1)):
        mapped = {field: row[index] if index < len(row) else None for index, field in mapping.items()} if mapping else _map_by_positions(row)
        mapped["_row_number"] = offset
        result.append(mapped)
    return result


def _find_client(db: Session, row: dict, sms: list[str], phones: list[str], emails: list[str]) -> tuple[Client | None, bool]:
    for phone_set, type_filter in ((sms, PhoneType.sms), (phones + sms, None)):
        if phone_set:
            query = select(Client).join(Phone).where(Phone.phone.in_(phone_set))
            if type_filter:
                query = query.where(Phone.type == type_filter)
            found = db.scalars(query).unique().all()
            if found:
                return found[0], len(found) > 1
    if emails:
        found = db.scalars(select(Client).join(Email).where(Email.email.in_(emails))).unique().all()
        if found:
            return found[0], len(found) > 1
    name, company = clean_text(row.get("name")), clean_text(row.get("company"))
    if name and company:
        found = db.scalars(select(Client).where(Client.name == name, Client.company == company)).all()
        if found:
            return found[0], len(found) > 1
    return None, False


def _sync_children(client: Client, emails: list[str], sms: list[str], common: list[str], places: list[str]) -> None:
    existing_emails = {email.email for email in client.emails}
    for email in dict.fromkeys(emails):
        if email not in existing_emails:
            client.emails.append(Email(email=email))
            existing_emails.add(email)
    existing_phones = {(phone.phone, phone.type) for phone in client.phones}
    for phone, phone_type in [(value, PhoneType.sms) for value in sms] + [(value, PhoneType.common) for value in common]:
        if (phone, phone_type) not in existing_phones:
            client.phones.append(Phone(phone=phone, type=phone_type))
            existing_phones.add((phone, phone_type))
    existing_places = {place.place for place in client.trade_places}
    for place in dict.fromkeys(places):
        if place not in existing_places:
            client.trade_places.append(TradePlace(place=place))
            existing_places.add(place)


def _fallback_name(row: dict, emails: list[str], sms: list[str], common: list[str]) -> str:
    return (
        clean_text(row.get("name"))
        or clean_text(row.get("company"))
        or clean_text(row.get("contact_person"))
        or clean_text(row.get("director"))
        or (emails[0] if emails else None)
        or (sms[0] if sms else None)
        or (common[0] if common else None)
        or f"Клиент из строки {row.get('_row_number', '')}".strip()
    )


def import_files(db: Session, files: list[tuple[str, bytes]]) -> ImportSummary:
    total = ImportSummary(files=len(files))
    for filename, content in files:
        imp = Import(file_name=filename)
        db.add(imp)
        db.flush()
        try:
            rows = _read_rows(filename, content)
            imp.rows_count = len(rows)
            total.rows += len(rows)
            for row in rows:
                row_number = int(row.get("_row_number") or 0) or None
                try:
                    created = False
                    duplicate = False
                    client_id: int | None = None
                    action = "client_updated"
                    with db.begin_nested():
                        emails = [email for email in (normalize_email(value) for value in split_values(row.get("emails"))) if email]
                        sms = [phone for phone in (normalize_phone(value) for value in split_values(row.get("sms_phones"))) if phone]
                        common = [phone for phone in (normalize_phone(value) for value in split_values(row.get("common_phones"))) if phone]
                        places = [place for place in (clean_text(value) for value in split_values(row.get("trade_places"))) if place]
                        name = _fallback_name(row, emails, sms, common)
                        client, duplicate = _find_client(db, row | {"name": name}, sms, common, emails)
                        data = dict(
                            name=name,
                            company=clean_text(row.get("company")),
                            price_type=clean_text(row.get("price_type")),
                            manager=clean_text(row.get("manager")),
                            birth_date=parse_date(row.get("birth_date")),
                            director=clean_text(row.get("director")),
                            contact_person=clean_text(row.get("contact_person")),
                            last_import_id=imp.id,
                        )
                        if client:
                            for key, value in data.items():
                                setattr(client, key, value)
                        else:
                            client = Client(**data, first_import_id=imp.id)
                            db.add(client)
                            created = True
                            action = "client_created"
                        _sync_children(client, emails, sms, common, places)
                        db.flush()
                        client_id = client.id
                    if duplicate:
                        total.duplicates += 1
                        db.add(ImportIssue(import_id=imp.id, row_number=row_number, level="warning", message="Найдено несколько совпадений клиента"))
                    if created:
                        imp.added_count += 1
                        total.added += 1
                    else:
                        imp.updated_count += 1
                        total.updated += 1
                    db.add(AuditLog(client_id=client_id, action=action, payload=filename))
                except Exception as exc:
                    imp.error_count += 1
                    total.errors += 1
                    db.add(ImportIssue(import_id=imp.id, row_number=row_number, level="error", message=str(exc)))
        except Exception as exc:
            imp.error_count += 1
            total.errors += 1
            db.add(ImportIssue(import_id=imp.id, level="error", message=str(exc)))
        db.commit()
    return total
