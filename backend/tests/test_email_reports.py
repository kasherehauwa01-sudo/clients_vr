from app.api.routes import DEFAULT_EMAIL_REPORTS, EXPORT_COLUMNS


def test_registry_export_exposes_requested_columns() -> None:
    assert list(EXPORT_COLUMNS) == ["name", "company", "manager", "phones", "emails"]
    assert [value[0] for value in EXPORT_COLUMNS.values()] == [
        "Наименование", "Фирма", "Менеджер", "Телефоны", "Email",
    ]


def test_email_update_contains_all_default_files_and_filters() -> None:
    reports = {report["name"]: report for report in DEFAULT_EMAIL_REPORTS}
    assert list(reports) == [
        "Корпоративные клиенты", "Розничные клиенты", "Пашута ОПТ",
        "Родина, Самойлова", "Трошина, Гончарова", "Шакулова",
        "Суркова, Ромащенко, Бабушкина, Новожилова", "Селянкина, Королева",
    ]
    assert reports["Корпоративные клиенты"]["price_types"] == ["Корпоративные"]
    assert reports["Розничные клиенты"]["counterparty_types"] == ["Частное лицо"]
    assert reports["Пашута ОПТ"]["managers"] == ["Пашута М.С.", "Пашута М.С. (Ростов)"]
    assert reports["Родина, Самойлова"]["managers"] == ["Родина", "Самойлова", "Родина Е.В. (Ростов)"]
