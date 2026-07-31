import logging
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.services import importer


def workbook(parser: str) -> importer.WorkbookRows:
    return importer.WorkbookRows(rows=[["Наименование"], ["Клиент"]], file_format=parser, sheet_count=1, sheet_name="Лист 1", parser=parser)


def test_ole_signature_uses_only_xlrd(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = workbook("xls")
    xlrd_parser = Mock(return_value=expected)
    xlsx_parser = Mock()
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", xlrd_parser)
    monkeypatch.setattr(importer, "_rows_from_xlsx", xlsx_parser)
    monkeypatch.setattr(importer.magic, "from_file", Mock(return_value="application/x-ole-storage"))

    result = importer._read_workbook("wrong.xlsx", importer.OLE_SIGNATURE + b"content")

    assert result is expected
    xlrd_parser.assert_called_once()
    xlsx_parser.assert_not_called()


def test_zip_signature_uses_only_openpyxl(monkeypatch: pytest.MonkeyPatch) -> None:
    expected = workbook("xlsx")
    xlrd_parser = Mock()
    xlsx_parser = Mock(return_value=expected)
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", xlrd_parser)
    monkeypatch.setattr(importer, "_rows_from_xlsx", xlsx_parser)
    monkeypatch.setattr(importer.magic, "from_file", Mock(return_value="application/zip"))

    result = importer._read_workbook("wrong.xls", b"PK" + b"content")

    assert result is expected
    xlsx_parser.assert_called_once()
    xlrd_parser.assert_not_called()


def test_unknown_signature_fails_before_any_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    xlrd_parser = Mock()
    xlsx_parser = Mock()
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", xlrd_parser)
    monkeypatch.setattr(importer, "_rows_from_xlsx", xlsx_parser)

    with pytest.raises(ValueError, match="Не удалось определить формат Excel по сигнатуре"):
        importer._read_workbook("КонтрагентыНаEmail_1.xls", b"not an excel file")

    xlrd_parser.assert_not_called()
    xlsx_parser.assert_not_called()


def test_parser_failure_logs_full_traceback(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(importer, "_rows_from_xls_xlrd", Mock(side_effect=AssertionError("broken OLE")))
    monkeypatch.setattr(importer.magic, "from_file", Mock(return_value="application/x-ole-storage"))
    caplog.set_level(logging.ERROR)

    with pytest.raises(AssertionError):
        importer._read_workbook("КонтрагентыНаEmail_1.xls", importer.OLE_SIGNATURE + b"content")

    assert "Traceback (most recent call last)" in caplog.text
    assert "AssertionError: broken OLE" in caplog.text
