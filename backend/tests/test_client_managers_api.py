import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, insert
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.api.sales_journal import client_managers_query, load_client_managers
from app.db.session import get_db
from app.main import app
from app.models.entities import Client, ClientStatus
from test_sales_journal_api import AUTH, api  # noqa: F401


def add_clients(rows):
    dependency = app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        db.execute(insert(Client), rows)
        db.commit()
    finally:
        dependency.close()


def legacy_mapping(payload):
    # Sales Journal clients_vr._text_value + normalize_client_name + _client_managers.
    result = {}
    for item in payload:
        name = str(item.get('client') or item.get('name') or '').strip()
        manager = str(item.get('manager') or '').strip()
        if name and manager:
            result[' '.join(name.split()).casefold()] = manager
    return result


@pytest.mark.parametrize('authorization', [None, 'Bearer wrong', 'Basic test-secret'])
def test_authorization(api: TestClient, authorization):
    response = api.get('/api/integration/client-managers', headers={} if authorization is None else {'Authorization': authorization})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'


def test_unconfigured_token(api: TestClient):
    from app.core.config import Settings, get_settings
    app.dependency_overrides[get_settings] = lambda: Settings(integration_token='')
    assert api.get('/api/integration/client-managers', headers=AUTH).status_code == 401


def test_mapping_matches_legacy_unicode_and_duplicates(api: TestClient):
    add_clients([
        {'name': 'Компания Дубль', 'manager': 'Первый'},
        {'name': ' компания дубль ', 'manager': ' Второй '},
        {'name': 'КОМПАНИЯ ДУБЛЬ', 'manager': '\t\u00a0'},
        {'name': 'Компания Дубль', 'manager': None},
        {'name': 'Компания Дубль', 'manager': 'Архивный', 'status': ClientStatus.archived},
        {'name': ' ООО\t  Ромашка\u00a0', 'manager': ' Один  Два '},
        {'name': 'ооо ромашка', 'manager': 'Другой'},
        {'name': 'Straße', 'manager': 'German'},
        {'name': 'STRASSE', 'manager': 'ASCII'},
        {'name': 'Σ', 'manager': 'Sigma'},
        {'name': 'ς', 'manager': 'Final sigma'},
        {'name': '\t\u00a0\n', 'manager': 'Пустое имя'},
        {'name': '', 'manager': 'Пустое имя'},
        {'name': 'Без владельца', 'manager': '\t '},
    ])
    old = api.get('/api/integration/clients', headers=AUTH).json()
    response = api.get('/api/integration/client-managers', headers=AUTH)
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/json'
    assert response.json() == legacy_mapping(old)
    assert response.json()['компания дубль'] == 'Второй'
    assert response.json()['ооо ромашка'] == 'Другой'
    assert 'Архивный' not in response.json().values()
    assert '' not in response.json()
    assert 'без владельца' not in response.json()
    assert response.json()['ооо бета'] == 'Иванов Иван'


def test_large_query_streams_scalar_rows_without_orm(api: TestClient):
    add_clients([{'name': f'Клиент {i % 100}', 'manager': f'Менеджер {i}'} for i in range(10000)])
    dependency = app.dependency_overrides[get_db]()
    db = next(dependency)
    def forbid_load(*args):
        pytest.fail('Client ORM entity loaded')
    event.listen(Client, 'load', forbid_load)
    try:
        mapping = load_client_managers(db)
        assert mapping['клиент 0'] == 'Менеджер 9900'
        assert mapping['клиент 99'] == 'Менеджер 9999'
        assert len(db.identity_map) == 0
    finally:
        event.remove(Client, 'load', forbid_load)
        dependency.close()
    assert api.get('/api/integration/client-managers', headers=AUTH).json() == mapping
    query = client_managers_query()
    assert [column.name for column in query.selected_columns] == ['id', 'name', 'manager', 'status']
    assert query.get_execution_options()['yield_per'] == 512
    assert 'ORDER BY lower(trim(clients.name)), clients.id' in str(query.compile(dialect=postgresql.dialect()))


def test_empty_mapping_and_openapi(api: TestClient):
    dependency = app.dependency_overrides[get_db]()
    db = next(dependency)
    try:
        db.query(Client).delete()
        db.commit()
    finally:
        dependency.close()
    assert api.get('/api/integration/client-managers', headers=AUTH).json() == {}
    operation = api.get('/openapi.json').json()['paths']['/api/integration/client-managers']['get']
    assert operation['security'] == [{'HTTPBearer': []}]
    schema = operation['responses']['200']['content']['application/json']['schema']
    assert schema['type'] == 'object'
    assert schema['additionalProperties'] == {'type': 'string'}
