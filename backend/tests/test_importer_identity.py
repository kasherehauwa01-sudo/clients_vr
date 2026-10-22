from io import BytesIO

import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models.entities import Client
from app.services.importer import import_files


def workbook(rows):
    book = Workbook()
    sheet = book.active
    sheet.append([
        'Наименование', 'Фирма', 'Места торговли', 'Контактное лицо',
        'Телефон', 'Email', 'Дата последней покупки',
    ])
    for row in rows:
        sheet.append(row)
    content = BytesIO()
    book.save(content)
    book.close()
    return content.getvalue()


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as session:
        yield session
    engine.dispose()


@pytest.mark.parametrize('distinct_field', [2, 3, 4])
def test_repeated_import_preserves_eight_namesakes(db, distinct_field):
    rows = []
    for index in range(8):
        row = ['Коралл', None, None, None, None, None, '01.10.2026']
        row[distinct_field] = f'Реквизит {index}'
        rows.append(row)
    first = import_files(db, [('clients.xlsx', workbook(rows))])
    assert (first.added, first.errors) == (8, 0), first.logs
    ids = list(db.scalars(select(Client.id).order_by(Client.id)))
    # New purchases must update existing cards rather than create more clients.
    for row in rows:
        row[6] = '22.10.2026'
    for _ in range(3):
        result = import_files(db, [('clients.xlsx', workbook(list(reversed(rows))))])
        assert (result.added, result.updated, result.errors) == (0, 8, 0), result.logs
    assert list(db.scalars(select(Client.id).order_by(Client.id))) == ids
    assert all(client.last_purchase_date.isoformat() == '2026-10-22' for client in db.scalars(select(Client)))


def test_name_only_repeated_import_does_not_grow_existing_duplicates(db):
    db.add_all([Client(name='Коралл'), Client(name='Коралл')])
    db.commit()
    result = import_files(db, [('clients.xlsx', workbook([['Коралл']]))])
    assert (result.added, result.updated, result.duplicates, result.errors) == (0, 1, 1, 0)
    assert len(db.scalars(select(Client)).all()) == 2


@pytest.mark.parametrize('company,phone,email', [
    ('Другая фирма', None, None),
    (None, '+79991112233', None),
    (None, None, 'client@example.com'),
])
def test_fallback_does_not_merge_with_different_company_or_contacts(db, company, phone, email):
    initial = import_files(db, [('clients.xlsx', workbook([['Коралл', company, None, None, phone, email]]))])
    assert initial.errors == 0, initial.logs
    result = import_files(db, [('clients.xlsx', workbook([['Коралл']]))])
    assert (result.added, result.errors) == (1, 0), result.logs
    repeated = import_files(db, [('clients.xlsx', workbook([['Коралл']]))])
    assert (repeated.added, repeated.updated, repeated.errors) == (0, 1, 0), repeated.logs
    assert len(db.scalars(select(Client)).all()) == 2
