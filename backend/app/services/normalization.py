import re
from datetime import date, datetime
from email_validator import EmailNotValidError, validate_email

PHONE_RE = re.compile(r"\d+")


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
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    if len(digits) < 7:
        return None
    return f"+{digits}" if not digits.startswith("+") else digits


def split_values(value: object) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [part.strip() for part in re.split(r"[;,\n]+", text) if part.strip()]


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
