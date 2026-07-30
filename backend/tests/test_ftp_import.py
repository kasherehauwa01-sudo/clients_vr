from app.services.ftp_import import select_xls_files


def test_select_xls_files_filters_and_sorts() -> None:
    names = [
        "clients3.xls", "clients1.xls", "error_clients.xls", "clients2.XLS",
        "clients.xlsx", "clients.xml", "clients.csv", "clients.zip", "clients.tmp",
    ]

    assert select_xls_files(names) == ["clients1.xls", "clients2.XLS", "clients3.xls"]
