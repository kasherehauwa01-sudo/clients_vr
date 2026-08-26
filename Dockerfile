FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/index.html frontend/vite.config.ts ./
COPY frontend/src ./src
RUN npm install && npm run build

FROM python:3.12-slim AS backend
WORKDIR /app
ENV CLIENTS_IMPORT_LOG=/app/logs/import.log
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /app/logs
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY --from=frontend /app/frontend/dist ./static
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'"]
