import re
from datetime import date, datetime


PHONE_GROUP_SEPARATOR_RE = re.compile(r"[;,|\r\n]+")
SECRET_FIELD_DENYLIST = {
    "password", "пароль", "password_hash", "token", "access_token",
    "refresh_token", "api_key", "secret", "database_url", "dsn",
}


def normalize_directory_phone(value: object) -> str | None:
    """Нормализует телефон для CallTrack до последних десяти цифр."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits[-10:] if len(digits) >= 10 else None


def extract_directory_phones(values: list[object]) -> list[str]:
    """Извлекает телефоны из строк с распространёнными разделителями."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in PHONE_GROUP_SEPARATOR_RE.split(str(value or "")):
            phone = normalize_directory_phone(part)
            if phone and phone not in seen:
                seen.add(phone)
                result.append(phone)
    return result


def extract_original_phone_values(values: list[object]) -> list[str]:
    """Разделяет несколько телефонов, сохраняя исходное форматирование."""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        for part in PHONE_GROUP_SEPARATOR_RE.split(str(value or "")):
            original = part.strip()
            normalized = normalize_directory_phone(original)
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(original)
    return result


def build_client_directory(rows: list[tuple[int, str, str]]) -> list[dict]:
    """Группирует результат одного SQL-запроса в публичный справочник."""
    clients: dict[int, dict] = {}
    raw_phones: dict[int, list[object]] = {}
    for client_id, name, phone in rows:
        clean_name = str(name or "").strip()
        if not clean_name:
            continue
        clients.setdefault(client_id, {"name": clean_name, "phones": []})
        raw_phones.setdefault(client_id, []).append(phone)
    result: list[dict] = []
    for client_id, client in clients.items():
        phones = extract_directory_phones(raw_phones.get(client_id, []))
        if phones:
            result.append({"name": client["name"], "phones": phones})
    return result


def _display_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def compact_fields(values: dict) -> dict:
    """Удаляет пустые и потенциально секретные поля карточки."""
    result = {}
    for key, value in values.items():
        if key.lower() in SECRET_FIELD_DENYLIST:
            continue
        value = _display_value(value)
        if value is None or value == "" or value == []:
            continue
        result[key] = value
    return result


def build_client_record(client, *, normalized_phones: bool) -> dict | None:
    name = str(client.name or "").strip()
    original_phones = extract_original_phone_values([phone.phone for phone in client.phones])
    phones = extract_directory_phones(original_phones) if normalized_phones else original_phones
    if not name or not phones:
        return None
    common_phones = [phone.phone for phone in client.phones if getattr(phone.type, "value", phone.type) == "common"]
    sms_phones = [phone.phone for phone in client.phones if getattr(phone.type, "value", phone.type) == "sms"]
    fields = compact_fields({
        "Наименование": name,
        "Тип цены": client.price_type,
        "Менеджер": client.manager,
        "Дата рождения": client.birth_date,
        "Email": list(dict.fromkeys(email.email for email in client.emails if email.email)),
        "Телефоны прочие": client.raw_common_phones or common_phones,
        "Места торговли": list(dict.fromkeys(place.place for place in client.trade_places if place.place)),
        "Телефоны для СМС и рассылки": client.raw_sms_phones or sms_phones,
        "Руководитель": client.director,
        "Фирма": client.company,
        "Контактное лицо": client.contact_person,
        "Источник клиента": client.client_source,
        "Дата последней покупки": client.last_purchase_date,
        "Вид покупателя": client.buyer_type,
        "Вид контрагента": client.counterparty_type,
        "Статус": getattr(client.status, "value", client.status),
        "Дата загрузки": client.created_at,
        "Дата обновления": client.updated_at,
    })
    return {"name": name, "phones": phones, "fields": fields}
