from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.entities import Client, Import, ImportIssue, Phone, PhoneType
from app.services.importer import import_files


def phone_workbook() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Наименование", "Фирма", "Телефоны прочие", "Телефоны для СМС и рассылки"])
    sheet.append(["Клиент", "Фирма", "8 (999) 111-22-33", "9994445566"])
    content = BytesIO()
    workbook.save(content)
    workbook.close()
    return content.getvalue()


@pytest.mark.parametrize("existing_client", [False, True])
def test_import_adds_normalized_phones_and_can_be_repeated(existing_client: bool) -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            if existing_client:
                db.add(Client(name="Клиент", company="Фирма"))
                db.commit()

            files = [("clients.xlsx", phone_workbook())]
            summary = import_files(db, files)

            assert summary.errors == 0, summary.logs
            assert summary.added == (0 if existing_client else 1)
            assert summary.updated == (1 if existing_client else 0)
            db.expire_all()
            client = db.scalars(select(Client)).one()
            assert {(phone.phone, phone.normalized_phone, phone.type) for phone in client.phones} == {
                ("+79991112233", "9991112233", PhoneType.common),
                ("+79994445566", "9994445566", PhoneType.sms),
            }

            repeated = import_files(db, files)

            assert repeated.errors == 0, repeated.logs
            assert repeated.added == 0
            assert repeated.updated == 1
            assert len(db.scalars(select(Client)).all()) == 1
            assert len(db.scalars(select(Phone)).all()) == 2
            assert all(record.error_count == 0 for record in db.scalars(select(Import)))
            assert db.scalars(select(ImportIssue).where(ImportIssue.level == "error")).all() == []
    finally:
        engine.dispose()
