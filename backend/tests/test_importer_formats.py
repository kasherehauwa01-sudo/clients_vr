import logging
from unittest.mock import Mock

import pytest

from app.services import importer


def workbook(parser: str) -> importer.WorkbookRows:
    return importer.WorkbookRows(rows=[["Наименование"], ["Клиент"]], file_format="xls", sheet_count=1, sheet_name="Лист 1", parser=parser)


def test_regular_xls_uses_xlrd(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    expected = workbook("xlrd")
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", Mock(return_value=expected))
    calamine = Mock()
    legacy = Mock()
    converter = Mock()
    monkeypatch.setattr(importer, "_rows_from_xls_calamine", calamine)
    monkeypatch.setattr(importer, "_rows_from_legacy_document", legacy)
    monkeypatch.setattr(importer, "_rows_from_xls_via_libreoffice", converter)

    caplog.set_level(logging.INFO)
    assert importer._rows_from_xls(b"binary-xls") is expected
    calamine.assert_not_called()
    legacy.assert_not_called()
    converter.assert_not_called()
    assert "Импорт XLS: xlrd" in caplog.text


def test_1c_xls_falls_back_to_calamine(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    expected = workbook("calamine")
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", Mock(side_effect=AssertionError()))
    monkeypatch.setattr(importer, "_rows_from_xls_calamine", Mock(return_value=expected))

    caplog.set_level(logging.INFO)
    assert importer._rows_from_xls(b"1c-xls") is expected
    assert "Импорт XLS: python-calamine" in caplog.text


def test_spreadsheet_xml_with_xls_extension_uses_legacy_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    content = b'''<?xml version="1.0" encoding="utf-8"?>
    <Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
      xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
      <Worksheet ss:Name="Clients"><Table><Row><Cell><Data ss:Type="String">Name</Data></Cell></Row></Table></Worksheet>
    </Workbook>'''

    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", Mock(side_effect=ValueError("not binary xls")))
    monkeypatch.setattr(importer, "_rows_from_xls_calamine", Mock(side_effect=RuntimeError("Cannot detect file format")))
    result = importer._rows_from_xls(content)

    assert result.parser == "legacy"
    assert result.sheet_name == "Clients"
    assert result.rows == [["Name"]]


def test_html_with_xls_extension_uses_legacy_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", Mock(side_effect=ValueError("not binary xls")))
    monkeypatch.setattr(importer, "_rows_from_xls_calamine", Mock(side_effect=RuntimeError("Cannot detect file format")))
    result = importer._rows_from_xls(b"<html><table><tr><th>Name</th></tr><tr><td>Client<br>One</td></tr></table></html>")

    assert result.parser == "legacy"
    assert result.rows == [["Name"], ["Client\nOne"]]


def test_broken_xls_reports_clear_error_and_logs_details(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", Mock(side_effect=AssertionError()))
    monkeypatch.setattr(importer, "_rows_from_xls_calamine", Mock(side_effect=RuntimeError("Cannot detect file format")))
    monkeypatch.setattr(importer, "_rows_from_legacy_document", Mock(side_effect=ValueError("неизвестное содержимое")))
    monkeypatch.setattr(importer, "_rows_from_xls_via_libreoffice", Mock(side_effect=ValueError("конвертация не удалась")))

    with pytest.raises(ValueError) as error:
        importer._rows_from_xls(b"broken")

    message = str(error.value)
    assert message.startswith("Не удалось определить формат XLS")
    assert "Проверены: xlrd, python-calamine, legacy parser и конвертация в XLSX" in message
    assert "Cannot detect file format" not in message
    assert "обработчик xlrd завершился ошибкой" in caplog.text
    assert "обработчик legacy parser завершился ошибкой" in caplog.text
    assert "обработчик LibreOffice → XLSX завершился ошибкой" in caplog.text
    assert "Cannot detect file format" in caplog.text


def test_unreadable_1c_xls_is_converted_to_xlsx(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    expected = workbook("libreoffice")
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", Mock(side_effect=AssertionError()))
    monkeypatch.setattr(importer, "_rows_from_xls_calamine", Mock(side_effect=RuntimeError("Cannot detect file format")))
    monkeypatch.setattr(importer, "_rows_from_legacy_document", Mock(side_effect=ValueError("unknown legacy format")))
    monkeypatch.setattr(importer, "_rows_from_xls_via_libreoffice", Mock(return_value=expected))

    caplog.set_level(logging.INFO)
    assert importer._rows_from_xls(b"1c-export") is expected
    assert "Импорт XLS: LibreOffice → XLSX" in caplog.text
