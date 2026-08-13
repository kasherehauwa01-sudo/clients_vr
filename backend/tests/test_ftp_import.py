from unittest.mock import Mock
from types import SimpleNamespace

from app.services import ftp_import
from app.services.ftp_import import FtpSettings, select_xls_files


def test_select_xls_files_filters_and_sorts() -> None:
    names = [
        "clients3.xls", "clients1.xls", "error_clients.xls", "clients2.XLS",
        "clients.xlsx", "clients.xml", "clients.csv", "clients.zip", "clients.tmp",
    ]

    assert select_xls_files(names) == ["clients1.xls", "clients2.XLS", "clients3.xls"]


def test_ftp_operation_reconnects_after_broken_control_connection(monkeypatch) -> None:
    first, second = Mock(), Mock()
    connections = iter([(first, "/xml/clients"), (second, "/xml/clients")])
    monkeypatch.setattr(ftp_import, "_connect", Mock(side_effect=lambda settings: next(connections)))
    monkeypatch.setattr(ftp_import, "sleep", Mock())
    operation = Mock(side_effect=[BrokenPipeError("broken"), "ok"])

    result = ftp_import._ftp_operation(FtpSettings(host="ftp", user="user"), "тест", operation)

    assert result == "ok"
    assert operation.call_count == 2
    first.quit.assert_called_once()
    second.quit.assert_called_once()


def test_import_error_details_contains_row_reasons() -> None:
    result = SimpleNamespace(
        errors=2,
        logs=[
            "Файл «clients.xls», строка 15. Причина: неверная дата. Что исправить: проверьте строку.",
            "Файл «clients.xls», строка 27. Причина: неверный телефон. Что исправить: проверьте строку.",
        ],
    )

    details = ftp_import._import_error_details(result)

    assert "строка 15" in details
    assert "неверная дата" in details
    assert details != "Импорт завершён с ошибками: 2"
