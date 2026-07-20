import re
from datetime import date, datetime
from email_validator import EmailNotValidError, validate_email

PHONE_RE = re.compile(r"\d+")
PHONE_IN_TEXT_RE = re.compile(
    r"(?<!\d)(?:\+?[78](?:[\s().-]*\d){10}|(?:\d[\s().-]*){9}\d)(?!\d)"
)


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).strip().split())
    return text or None


def normalize_phone(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    digits = "".join(PHONE_RE.findall(text))
    if len(digits) == 10:
        digits = "7" + digits
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) != 11 or not digits.startswith("7"):
        return None
    return f"+{digits}"


def extract_phones(value: object) -> list[str]:
    """Находит все российские номера внутри текста с именами и адресами."""
    if value is None:
        return []
    phones = [normalize_phone(match.group()) for match in PHONE_IN_TEXT_RE.finditer(str(value))]
    return list(dict.fromkeys(phone for phone in phones if phone))


def split_values(value: object) -> list[str]:
    if value is None:
        return []
    # Переносы строк, запятые, точки с запятой и разделитель "||" в Excel
    # означают отдельные значения. Делим до clean_text, чтобы не потерять границы строк.
    parts = re.split(r"\s*\|\|\s*|[;,\r\n]+", str(value))
    return [text for part in parts if (text := clean_text(part))]


def repair_legacy_excel_text(value: object) -> object:
    """Исправляет кириллицу из старых XLS, ошибочно декодированную как Latin-1."""
    if not isinstance(value, str) or not value:
        return value
    try:
        repaired = value.encode("latin1").decode("cp1251")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    original_cyrillic = sum("а" <= char.lower() <= "я" or char.lower() == "ё" for char in value)
    repaired_cyrillic = sum("а" <= char.lower() <= "я" or char.lower() == "ё" for char in repaired)
    return repaired if repaired_cyrillic > original_cyrillic else value


def normalize_email(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return validate_email(text, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        return None


def parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = clean_text(value)
    if not text:
        return None
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
