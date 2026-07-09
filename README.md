# Clients VR

Веб-приложение для ведения базы клиентов с импортом Excel, быстрым поиском, фильтрами, экспортом, массовыми операциями и журналами.

## Стек

- Backend: FastAPI, SQLAlchemy 2, Alembic, PostgreSQL/SQLite, openpyxl/xlrd, XlsxWriter.
- Frontend: React, Vite, TypeScript.
- Deploy: Docker Compose + PostgreSQL + Nginx.

## Возможности

- Серверная пагинация, поиск, фильтрация и сортировка клиентов.
- Карточка клиента с основной информацией, контактами и историей импортов.
- Импорт нескольких `.xls`/`.xlsx` файлов с защитой от дублей.
- Поиск существующего клиента при импорте по приоритету: SMS-телефон, любой телефон, email, наименование + фирма.
- История импортов, журнал ошибок/конфликтов и журнал действий.
- Экспорт списка клиентов в Excel.
- Массовое удаление, архивирование, смена менеджера и типа цены.

## Быстрый запуск

```bash
docker compose up --build
```

Откройте http://localhost:8080.

## Миграции

В Docker миграции применяются автоматически перед стартом приложения. Для ручного запуска:

```bash
cd backend
CLIENTS_DATABASE_URL=postgresql+psycopg://clients:clients@localhost:5432/clients alembic upgrade head
```

## Локальная разработка

Backend:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```
