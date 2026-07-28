from app.services.normalization import extract_emails


def test_extract_emails_removes_surrounding_text_and_normalizes() -> None:
    value = "Иван Петров < SALES@Example.COM >; резерв: info@example.org, телефон +7 999 111-22-33"

    assert extract_emails(value) == ["sales@example.com", "info@example.org"]


def test_extract_emails_ignores_invalid_values_and_duplicates() -> None:
    value = "не email: user@localhost; valid@example.com; VALID@example.com"

    assert extract_emails(value) == ["valid@example.com"]
