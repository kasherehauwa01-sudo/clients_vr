# Clients VR для kvasmix.ru

Веб-приложение для ведения базы клиентов. Проект подготовлен для размещения внутри существующего сайта по адресу:

```text
https://kvasmix.ru/vr/clients/
```

Приложение учитывает подкаталог `/vr/clients/` во frontend-сборке, API, статических файлах и nginx-проксировании.

## Возможности

- Список клиентов с серверной пагинацией, поиском, фильтрацией и сортировкой.
- Карточка клиента с основной информацией, контактами и историей импортов.
- Массовый импорт `.xls` и `.xlsx` файлов.
- Защита от дублей при импорте по приоритету: SMS-телефон, любой телефон, email, наименование + фирма.
- История импортов, журнал ошибок/конфликтов и журнал действий.
- Экспорт списка клиентов в Excel.
- Массовое удаление, архивирование, смена менеджера и типа цены.

## Структура размещения

- Внешний адрес приложения: `/vr/clients/`.
- Внешний адрес API: `/vr/clients/api/`.
- FastAPI внутри контейнера слушает порт `8000`.
- Docker Compose публикует порт только локально: `127.0.0.1:8015:8000`.
- Основной nginx сервера `kvasmix.ru` проксирует `/vr/clients/` на `http://127.0.0.1:8015/vr/clients/`.

## Установка Docker на Ubuntu

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
```

## Первый запуск

```bash
git clone <URL_РЕПОЗИТОРИЯ> /opt/clients_vr
cd /opt/clients_vr
docker compose up -d --build
```

После настройки nginx приложение будет доступно по адресу:

```text
https://kvasmix.ru/vr/clients/
```

## Обновление проекта без потери данных

Данные PostgreSQL хранятся в Docker volume `clients_vr_postgres_data` и не удаляются при пересборке контейнеров.

```bash
cd /opt/clients_vr
git pull
docker compose up -d --build
```

При старте контейнера автоматически выполняется:

```bash
alembic upgrade head
```

Миграции рассчитаны на повторный запуск контейнера и не должны ломать существующий Docker volume.

## Настройка основного nginx сервера

В репозитории есть готовый фрагмент:

```text
nginx/kvasmix-vr-clients.conf
```

Добавьте его содержимое внутрь существующего блока `server { ... }` для `kvasmix.ru`:

```nginx
location /vr/clients/ {
    proxy_pass http://127.0.0.1:8015/vr/clients/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /vr/clients;
    proxy_redirect off;
    client_max_body_size 100m;
    proxy_connect_timeout 30s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;
    send_timeout 600s;
}

location = /vr/clients {
    return 301 /vr/clients/;
}
```

Проверка и перезагрузка nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Такой `location` поддерживает:

- API `/vr/clients/api/`;
- React SPA;
- обновление страницы браузером;
- прямые переходы по внутренним ссылкам;
- загрузку статических файлов `/vr/clients/assets/...`.

## Резервное копирование PostgreSQL

```bash
cd /opt/clients_vr
mkdir -p backups
docker compose exec -T postgres pg_dump -U clients -d clients > backups/clients_$(date +%F_%H-%M).sql
```

## Восстановление PostgreSQL из backup

Осторожно: команда ниже очищает текущую базу перед восстановлением.

```bash
cd /opt/clients_vr
docker compose exec -T postgres psql -U clients -d clients -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
docker compose exec -T postgres psql -U clients -d clients < backups/clients_YYYY-MM-DD_HH-MM.sql
docker compose up -d --build
```

## Проверка конфигурации размещения

Перед деплоем можно выполнить быструю проверку настроек подкаталога, nginx, Docker Compose и Alembic:

```bash
python scripts/deployment_smoke_check.py
```

Сборка frontend должна формировать ссылки вида `/vr/clients/assets/...`:

```bash
cd frontend
npm install
npm run build
```

## Локальная разработка

Backend:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
CLIENTS_PUBLIC_BASE_PATH=/vr/clients uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Для локальной Vite-разработки можно задать API явно:

```bash
VITE_API_URL=http://127.0.0.1:8000/vr/clients/api npm run dev
```

## Автозагрузка клиентов по FTP

Скопируйте `.env.example` в `.env` и заполните `FTP_HOST`, `FTP_PORT`,
`FTP_USER`, `FTP_PASSWORD` и `FTP_DIRECTORY`. Учетные данные не задаются в
исходном коде. Расписание управляется переменными `FTP_RUN_TIME` (по умолчанию
`23:59` по Москве), `FTP_RETRY_MINUTES` и `FTP_MAX_ATTEMPTS`.

Настройки можно изменить без перезагрузки страницы в разделе **Настройки →
Автозагрузка**. Файл `.env` подключен к контейнеру как bind mount, поэтому
изменения интерфейса сохраняются между перезапусками. Автозагрузка принимает
только `.xls`; файлы с префиксом `error_` и остальные форматы игнорируются.

## JSON API справочника клиентов для CallTrack

Read-only endpoint `GET /api/get_clients.php` возвращает только активных клиентов
с непустым наименованием и хотя бы одним телефоном. Телефоны представлены
массивом уникальных строк из последних 10 цифр. Публичный URL при стандартном
base path: `https://kvasmix.ru/vr/clients/api/get_clients.php`.

Полная карточка по телефону доступна без пагинации через
`GET /api/client_card.php?phone=9991234567`. Поиск сравнивает последние 10 цифр
и возвращает все совпадения, если один телефон связан с несколькими клиентами.
Ответ содержит только разрешённые бизнес-поля; пустые и секретные значения не
передаются.
