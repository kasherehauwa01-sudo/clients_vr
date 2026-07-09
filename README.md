# Clients VR

Веб-приложение для ведения базы клиентов с импортом Excel, быстрым поиском, фильтрами, экспортом и журналами.

## Стек

- Backend: FastAPI, SQLAlchemy, PostgreSQL/SQLite, openpyxl/xlrd, XlsxWriter.
- Frontend: React, Vite, TypeScript.
- Deploy: Docker Compose + PostgreSQL + Nginx.

## Быстрый запуск

```bash
docker compose up --build
```

Откройте http://localhost:8080.

## Локальная разработка

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```
