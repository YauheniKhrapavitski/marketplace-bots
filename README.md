# WB Feedback Telegram Assistant

Telegram-бот для продавца Wildberries. MVP получает неотвеченные отзывы через WB Feedbacks API, выбирает ответ из утверждённых шаблонов, показывает карточку оператору в Telegram и отправляет ответ только после подтверждения.

## Что входит в MVP

- Один Telegram-бот и один кабинет продавца Wildberries.
- Доступ только для Telegram ID из `TELEGRAM_ADMIN_IDS`.
- WB API token хранится в базе в зашифрованном виде.
- Синхронизация неотвеченных отзывов по расписанию и вручную через `/sync`.
- Подбор шаблона по товару, ключевым словам, рейтингу и fallback.
- Автоответ на отзывы 5 из 5 из утверждённых шаблонов.
- Ручное подтверждение, пропуск, перенос и игнорирование отзывов с другими оценками.
- История действий, health/readiness endpoints, Alembic migration, Docker Compose.

## Что не входит

Нет генерации ответов через LLM, автоотправки без подтверждения для оценок ниже 5, вопросов покупателей, чатов, web UI, нескольких продавцов, ролей, CRM и биллинга.

## Требования

- Docker и Docker Compose.
- Для локального запуска без Docker: Python 3.12 и PostgreSQL 16.

## Telegram BotFather

1. Откройте `@BotFather`.
2. Выполните `/newbot`.
3. Сохраните токен в `TELEGRAM_BOT_TOKEN`.
4. Узнайте Telegram ID операторов и укажите их через запятую в `TELEGRAM_ADMIN_IDS`.

## Wildberries Token

Создайте токен в кабинете продавца Wildberries с доступом к отзывам. Для sandbox используйте:

```env
WB_API_BASE_URL=https://feedbacks-api-sandbox.wildberries.ru
WB_ENVIRONMENT=sandbox
```

Для production:

```env
WB_API_BASE_URL=https://feedbacks-api.wildberries.ru
WB_ENVIRONMENT=production
```

## Настройка

Скопируйте `.env.example` в `.env` и заполните обязательные переменные:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_ADMIN_IDS=123456789
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/wb_assistant
WB_API_BASE_URL=https://feedbacks-api-sandbox.wildberries.ru
WB_API_TOKEN=
WB_ENVIRONMENT=sandbox
APP_ENCRYPTION_KEY=change-me-long-random-secret
BRAND_NAME=
ANSWER_SIGNATURE=
```

`APP_ENCRYPTION_KEY` должен быть стабильным: при его замене сохранённые WB токены нельзя будет расшифровать.

## Запуск через Docker

```bash
docker compose up --build
```

Сервис `bot` применяет миграции и запускает FastAPI, Telegram polling и scheduler. Health endpoint доступен на `http://localhost:8000/health`.

## Миграции

```bash
make migrate
```

В Docker миграция выполняется автоматически перед стартом приложения.

## Шаблоны

Стартовые шаблоны добавляются сервисом при первой синхронизации или через `/templates`. Логика выбора:

1. товар + ключевое слово;
2. товар + рейтинг;
3. общее ключевое слово;
4. общий рейтинг;
5. fallback.

## Команды бота

- `/start` - приветствие.
- `/status` - состояние интеграции.
- `/reviews` - следующий отзыв.
- `/sync` - ручная синхронизация.
- `/templates` - список шаблонов.
- `/settings` - настройки.
- `/history` - последние операции.
- `/help` - справка.

## Проверка интеграции

1. Заполните `.env`.
2. Запустите `docker compose up --build`.
3. Откройте `/health`.
4. Напишите боту `/start`.
5. Запустите `/sync`.
6. Проверьте `/reviews`.

## Тесты и качество

```bash
ruff check .
mypy app
pytest
```

Или:

```bash
make lint
make typecheck
make test
```

## Типовые ошибки

- `Wildberries отклонил API-токен`: проверьте токен и права.
- `/ready` возвращает `503`: не заполнены обязательные переменные или недоступна база.
- Нет отзывов: проверьте режим sandbox/production и наличие неотвеченных отзывов.
- Ошибки `429`: клиент повторяет запросы с `Retry-After` и exponential backoff.

## Резервное копирование PostgreSQL

Создать backup:

```bash
docker compose exec db pg_dump -U postgres wb_assistant > backup.sql
```

Восстановить backup:

```bash
docker compose exec -T db psql -U postgres wb_assistant < backup.sql
```

## Wildberries Google Sheets Export Agent

Agent `wb_export_agent.py` exports fresh Wildberries API data into an existing
Google Sheets spreadsheet. It reads API keys only from the `API ключ` sheet, does
not copy old data from other sheets, and writes to `Выгрузки` only after all
requested API reports have been fetched successfully.

Expected key layout:

- column A label containing `Контент`, token in the same row in column B;
- column A label containing `Цены и скидки`, token in the same row in column B;
- fallback cells: `B1` for content and `B3` for prices.

Run:

```bash
python wb_export_agent.py --spreadsheet "https://docs.google.com/spreadsheets/d/.../edit"
python wb_export_agent.py --spreadsheet "https://docs.google.com/spreadsheets/d/.../edit" --report all
python wb_export_agent.py --spreadsheet "https://docs.google.com/spreadsheets/d/.../edit" --report nomenclatures
python wb_export_agent.py --spreadsheet "https://docs.google.com/spreadsheets/d/.../edit" --report prices
python wb_export_agent.py --spreadsheet "https://docs.google.com/spreadsheets/d/.../edit" --dry-run
```

Google authorization uses a service account. Set one of these variables before
running the agent:

```bash
set GOOGLE_SERVICE_ACCOUNT_FILE=C:\path\to\service-account.json
```

or:

```bash
set GOOGLE_SERVICE_ACCOUNT_JSON={...}
```

Share the target spreadsheet with the service account `client_email`. Before
writing, the agent creates a timestamped Google Drive copy as a backup, then
clears and rewrites only the `Выгрузки` sheet. Logs are structured JSON and never
include API tokens.
## TTN PDF Bot

This repository also contains a standalone Telegram bot for filling TTN PDF documents and
exporting extracted invoice data to Excel.

### Local Run

1. Copy `.env.example` to `.env`.
2. Fill `BOT_TOKEN`. Leave `ALLOWED_USER_IDS` empty to allow every Telegram user, or set
   comma-separated Telegram IDs.
3. Install dependencies:

```bash
make install
```

4. Run the TTN bot:

```bash
make run-ttn
```

### Docker Run

```bash
docker compose up -d --build
```

The bot stores SQLite data in `data/bot.sqlite3` and temporary job files in `tmp/ttn_jobs`.
The source PDF is never modified. Filled files are created inside the job directory and sent
back to the Telegram user.

PDF field placement is configured in `config/ttn_templates/ozon_ttn_a4.json`.

Only one Telegram polling instance may run for a bot token. Use either Docker Compose or
`make run-ttn`, not both at the same time. `scripts/start-bot.ps1` stops a local
`python -m ttn_bot.main` process before starting Docker to avoid Telegram `getUpdates`
conflicts.

## Ozon Reviews Bot Deployment

Ozon Reviews runs as a separate Compose project with its own PostgreSQL container,
Docker network, and persistent volume. Do not combine this file with `docker-compose.yml`;
that file owns the working WB Reviews and Ozon TTN services.

On the server, create the private environment file and fill its required values:

```bash
cp .env.ozon.example .env.ozon
nano .env.ozon
chmod 600 .env.ozon
```

Use an alphanumeric value for `OZON_DB_PASSWORD` (for example, output from
`openssl rand -hex 24`). Keep `APP_ENCRYPTION_KEY` stable after the first successful
sync because it encrypts the stored Ozon API key.

Deploy or update only Ozon Reviews:

```bash
sh scripts/deploy-ozon-reviews.sh
```

Inspect only the Ozon project:

```bash
docker compose --project-name marketplace-bots-ozon-reviews --env-file .env.ozon -f docker-compose.ozon-server.yml ps
docker compose --project-name marketplace-bots-ozon-reviews --env-file .env.ozon -f docker-compose.ozon-server.yml logs --tail=100 ozon-reviews-bot
```

The Ozon database has no published host port and is not shared with WB Reviews. Never
run `down -v` unless permanent deletion of the Ozon Reviews database is intended.
