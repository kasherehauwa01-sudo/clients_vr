from unittest.mock import Mock

import pytest

from app.services import importer


def workbook(parser: str) -> importer.WorkbookRows:
    return importer.WorkbookRows(rows=[["Наименование"], ["Клиент"]], file_format="xls", sheet_count=1, sheet_name="Лист 1", parser=parser)


def test_regular_xls_uses_xlrd(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = workbook("xlrd")
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", Mock(return_value=expected))
    calamine = Mock()
    legacy = Mock()
    monkeypatch.setattr(importer, "_rows_from_xls_calamine", calamine)
    monkeypatch.setattr(importer, "_rows_from_legacy_document", legacy)

    assert importer._rows_from_xls(b"binary-xls") is expected
    calamine.assert_not_called()
    legacy.assert_not_called()


def test_1c_xls_falls_back_to_calamine(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = workbook("calamine")
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", Mock(side_effect=AssertionError()))
    monkeypatch.setattr(importer, "_rows_from_xls_calamine", Mock(return_value=expected))

    assert importer._rows_from_xls(b"1c-xls") is expected


def test_spreadsheet_xml_with_xls_extension_uses_legacy_parser() -> None:
    content = b'''<?xml version="1.0" encoding="utf-8"?>
    <Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
      xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
      <Worksheet ss:Name="Clients"><Table><Row><Cell><Data ss:Type="String">Name</Data></Cell></Row></Table></Worksheet>
    </Workbook>'''

    result = importer._rows_from_legacy_document(content)

    assert result.parser == "legacy"
    assert result.sheet_name == "Clients"
    assert result.rows == [["Name"]]


def test_html_with_xls_extension_uses_legacy_parser() -> None:
    result = importer._rows_from_legacy_document(b"<html><table><tr><th>Name</th></tr><tr><td>Client<br>One</td></tr></table></html>")

    assert result.parser == "legacy"
    assert result.rows == [["Name"], ["Client\nOne"]]


def test_broken_xls_reports_all_parser_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", Mock(side_effect=AssertionError()))
    monkeypatch.setattr(importer, "_rows_from_xls_calamine", Mock(side_effect=RuntimeError("Cannot detect file format")))
    monkeypatch.setattr(importer, "_rows_from_legacy_document", Mock(side_effect=ValueError("неизвестное содержимое")))

    with pytest.raises(ValueError) as error:
        importer._rows_from_xls(b"broken")

    message = str(error.value)
    assert message.startswith("Не удалось определить внутренний формат XLS")
    assert "xlrd:" in message
    assert "calamine: RuntimeError (формат не распознан)" in message
    assert "legacy:" in message
    assert "Cannot detect file format" not in message
