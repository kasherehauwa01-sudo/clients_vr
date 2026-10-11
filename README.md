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

В фильтрах «Тип цены», «Вид покупателя» и «Вид контрагента» доступно
виртуальное значение `Не заполнено`. Frontend передаёт эту строку как обычное
значение соответствующего query-параметра (`price_type`, `buyer_type` или
`counterparty_type`), а backend выбирает записи с `NULL`, пустой строкой или
строкой только из пробелов. В базу значение `Не заполнено` не записывается.

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
передаются. Поиск использует существующий индекс `ix_phones_phone`, не загружает
полный справочник и возвращает в заголовке `Server-Timing` длительность SQL и
полное время формирования ответа.

### Инкрементальная синхронизация CallTrack

Для уже актуального полного кэша CallTrack запрашивает текущую границу журнала:

```text
GET /api/clients/changes/state
```

Дальнейшие страницы запрашиваются через
`GET /api/clients/changes?after_id=12345&limit=500`. `limit` по умолчанию равен
500 и ограничен 2000. Ответ содержит `items`, `next_after_id` и `has_more`.
Операция `upsert` включает полный снимок `client`, а `delete` содержит
`client_id` и удаляет либо деактивирует запись в кэше. Cursor — монотонный
`change_id`: следующему запросу передаётся ровно полученный `next_after_id`.
Повторная обработка страницы безопасна, поскольку upsert и delete идемпотентны.
Если полный refresh выполняется заново, безопасная последовательность от гонок:
получить `last_change_id` **до** refresh, загрузить справочник, затем прочитать
delta от сохранённого cursor до `has_more=false`.

Пример страницы:

```json
{
  "status": "success",
  "items": [
    {"change_id": 124, "operation": "upsert", "client_id": 10,
     "changed_at": "2026-08-13T12:00:00", "client": {"id": 10, "name": "ООО Ромашка", "phones": ["+79991234567"]}},
    {"change_id": 125, "operation": "delete", "client_id": 11,
     "changed_at": "2026-08-13T12:00:01"}
  ],
  "next_after_id": 125,
  "has_more": false
}
```


## Integration API для «Журнала продаж»

Базовый production URL для `CLIENTS_VR_API_URL`:

```text
https://kvasmix.ru/vr/clients/api
```

Все методы `/api/integration/*` используют единый Bearer-токен из переменной
`CLIENTS_INTEGRATION_TOKEN`. Значение токена передаётся только в заголовке
`Authorization` и не должно попадать в URL или логи.

### Менеджеры и клиенты

- `GET /api/integration/managers` — уникальные менеджеры;
- `GET /api/integration/clients` — клиенты интеграции;
- `GET /api/integration/clients?manager=Иванов Иван` — клиенты менеджера.

Существующие совместимые методы `GET /api/managers` и
`GET /api/clients?manager=...` сохраняют прежний формат массива строк.

### Виды покупателей

`GET /api/integration/buyer-types` возвращает уникальные непустые значения поля
«Вид покупателя» из неархивных клиентов:

```json
["HoReCa", "Розница"]
```

`GET /api/integration/clients?buyer_type=HoReCa` фильтрует клиентов по точному
значению без учёта регистра и внешних пробелов. Неизвестное значение возвращает
пустой массив. Фильтр `buyer_type` можно комбинировать с `manager`; в этом случае
клиент должен удовлетворять обоим условиям.

```json
[
  {
    "id": 123,
    "client": "ООО Ромашка",
    "name": "ООО Ромашка",
    "manager": "Иванов Иван",
    "buyer_type": "HoReCa"
  }
]
```

Совместимый вложенный endpoint
`GET /api/integration/buyer-types/{buyer_type}/clients` возвращает тот же формат.
Клиенты без заполненного вида покупателя в нефильтрованной выдаче получают
`"buyer_type": null`.

```bash
curl \
  -H "Authorization: Bearer $CLIENTS_INTEGRATION_TOKEN" \
  "https://kvasmix.ru/vr/clients/api/integration/buyer-types"

curl -G \
  -H "Authorization: Bearer $CLIENTS_INTEGRATION_TOKEN" \
  --data-urlencode "buyer_type=HoReCa" \
  "https://kvasmix.ru/vr/clients/api/integration/clients"
```

### Облегчённое соответствие клиентов и менеджеров

`GET /api/integration/client-managers` (тот же Bearer-токен) возвращает
JSON-объект `dict[str, str]` без обёртки; отсутствие соответствий — `{}`:

```json
{"ооо ромашка":"Иванов Иван","strasse":"Менеджер"}
```

Ключ вычисляется **точно** как в Sales Journal:
`" ".join(name.split()).casefold()` — удаление внешних и сжатие внутренних
Unicode-пробелов, Unicode casefold (например, `Straße` → `strasse`).
Значение — `manager.strip()`, с сохранением регистра и внутренних пробелов.
Архивные клиенты, пустые нормализованные имена и пустые менеджеры исключены.
Побеждает последний **непустой** менеджер в прежнем порядке
`lower(trim(name)), id`; это не обязательно запись с максимальным id среди
всех Python-нормализованных дубликатов. Пустой менеджер не удаляет соответствие.

Проверенный источник алгоритма: Sales Journal,
`backend/app/services/clients_vr.py`, функции `normalize_client_name`,
`_text_value`, `_client_managers`, commit
`0f4fe1441332de439b721945e0164ab41a3bfdff`.
SQL lower/trim не эквивалентны Python split/casefold, поэтому SQL-дедупликация
намеренно не применяется: она может изменить победителя и результат аналитики.

Запрос выбирает только `id, name, manager, status`, сохраняя SQL-фильтры старого
API. PostgreSQL отдаёт строки через серверный курсор с `yield_per=512`;
ORM Client и полный список строк не создаются. Память приложения составляет
O(U + 512), где U — число уникальных имён с менеджером, плюс сериализованный
JSON (и временная строка при UTF-8-кодировании). FastAPI получает готовый Response,
поэтому не копирует словарь для валидации. Это не фиксированный потолок памяти:
размер результата растёт с U; сортировка PostgreSQL также требует ресурсов БД.
Endpoint уменьшает расход памяти этого запроса, но сам по себе не доказывает
причину ранее наблюдавшихся OOM и не гарантирует их полное устранение.

Будущий клиент Sales Journal должен запрашивать
`https://kvasmix.ru/vr/clients/api/integration/client-managers` и использовать
JSON-объект непосредственно как словарь. При существующем
`CLIENTS_VR_API_URL=https://kvasmix.ru/vr/clients/api` путь запроса —
`/integration/client-managers`. Текущий `_client_managers` ожидает массив и
**не умеет** читать новый объект: в отдельном обновлении Sales Journal нужно
добавить получение/проверку `dict[str, str]` для этого endpoint и сохранить
старый parser только для fallback на `/integration/clients` при 404/405.
401/403 с настроенным токеном не должны вызывать fallback. При переключении
сбросить кэш `client-managers` или дождаться его TTL (300 секунд).
Другие вызовы `/integration/clients`, например загрузка buyer types/metadata,
нужно оценивать отдельно; эта доработка их автоматически не переключает.

### Безопасное обновление Clients VR после принятия PR

Эти действия выполняет оператор; production в рамках доработки не обновлялся.
Сначала проверить новую версию на staging с PostgreSQL 16 и сравнить словарь
с результатом старого алгоритма, включая Unicode и дубликаты.

1. Запланировать короткое окно обслуживания. В каталоге
   `/var/www/html/vr/clients` проверить `git status --short` (чистое дерево),
   сохранить `git rev-parse HEAD` и идентификатор текущего образа
   `docker compose images app`. Сохранить `.env` в защищённом месте и сделать
   резервную копию БД командой из раздела резервного копирования выше.
2. После merge PR получить изменения: `git fetch origin`, затем
   `git merge --ff-only origin/main`. Убедиться, что установлен согласованный
   commit, `.env` и `CLIENTS_INTEGRATION_TOKEN` сохранены.
3. На VPS с малым объёмом RAM предпочтительно собирать образ вне VPS и переносить
   его по принятой процедуре. Если сборка выполняется на VPS, делать это в окно
   обслуживания с контролем `free -h` и `docker stats`; команда сборки —
   `docker compose build app`. Не запускать параллельно тяжёлые отчёты.
4. После успешной сборки обновить только приложение:
   `docker compose up -d --no-deps app`. PostgreSQL и volumes сохраняются;
   изменения схемы, Compose, RAM и Swap для этого endpoint не нужны.
5. Проверить `docker compose ps`, `docker compose logs --tail=50 app` и
   `http://127.0.0.1:8015/vr/clients/api/health`. Проверить новый endpoint
   с Bearer-токеном безопасным инструментом (без записи токена в историю/логи),
   HTTP 200 и JSON-объект; без токена должен быть 401. Проверить старые endpoints.
   Наблюдать память во время реального запроса.
6. Только после проверки Clients VR переключить клиент Sales Journal на новый
   контракт. До этого существующая интеграция продолжает работать.
7. При сбое вернуть прежний образ приложения по сохранённому идентификатору
   (при необходимости восстановить прежний commit и пересобрать app), затем
   `docker compose up -d --no-deps app`. Если Sales Journal уже переключён,
   вернуть прежний путь/parser. БД откатывать не требуется: миграций нет.

Не использовать для этого обновления `docker compose down -v` или очистку БД.
