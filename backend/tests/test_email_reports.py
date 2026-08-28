from app.api.routes import DEFAULT_EMAIL_REPORTS, EXPORT_COLUMNS, _email_report_filename
from app.models.entities import Client


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
    assert all("counterparty_types" not in report for report in reports.values())
    assert reports["Пашута ОПТ"]["managers"] == ["Пашута М.С.", "Пашута М.С. (Ростов)"]
    assert reports["Родина, Самойлова"]["managers"] == ["Родина", "Самойлова", "Родина Е.В. (Ростов)"]


def test_email_report_uses_original_card_email_field() -> None:
    assert Client.__table__.c.raw_email.type.python_type is str
    assert Client.__table__.c.raw_email_source_known.type.python_type is bool


def test_email_report_filename_ends_with_data_row_count() -> None:
    used_names: set[str] = set()
    assert _email_report_filename("Корпоративные клиенты", 1889, 1, used_names) == (
        "Корпоративные клиенты. 1889.xlsx"
    )


def test_duplicate_email_report_names_keep_count_and_are_unique() -> None:
    used_names = {"корпоративные клиенты. 1889.xlsx"}
    assert _email_report_filename("Корпоративные клиенты", 1889, 2, used_names) == (
        "Корпоративные клиенты (2). 1889.xlsx"
    )
