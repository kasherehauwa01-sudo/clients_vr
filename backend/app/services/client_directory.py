import re


PHONE_GROUP_SEPARATOR_RE = re.compile(r"[;,|\r\n]+")


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
