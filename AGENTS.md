# AGENTS.md

## Project

Telegram assistant for Wildberries seller feedback replies. The MVP fetches unanswered WB feedbacks, selects a pre-approved template, shows it to an authorized Telegram operator, and sends the answer only after confirmation.

## Audience

Small Wildberries sellers or operators who manually control customer-facing review replies.

## Current Goal

Maintain the working WB Reviews, Ozon Reviews, and Ozon TTN bots plus the standalone Wildberries Excel export agent without mixing their workflows or deployment state.

## Non-Goals

No generative AI answers, no web UI for the Wildberries feedback MVP, no multiple sellers, no billing. Four- and five-star feedback can be published automatically from approved templates. One-, two-, and three-star feedback uses complaint-topic templates only when the topic is recognized; unclear negative feedback remains for manual handling. Buyer questions are a separate planned feature and must not reuse review templates, review statuses, or review commands. Ozon reviews are a separate planned feature with a separate Telegram bot and must not reuse Wildberries review or question templates, statuses, commands, or API clients. Cutter cabinets are a separate planned web application and must not reuse Telegram bot commands, WB/Ozon review templates, or review/question statuses.

## Stack

Python 3.12, aiogram 3.x, FastAPI, PostgreSQL 16, SQLAlchemy 2.x async ORM, Alembic, APScheduler, httpx, Pydantic Settings, Docker Compose, pytest, Ruff, mypy.

## Key Folders

- `app/bot`: Telegram routers, keyboards, user-facing messages.
- `app/api`: FastAPI health and readiness endpoints.
- `app/db`: SQLAlchemy session and models.
- `app/repositories`: database access boundaries.
- `app/services`: business workflows and idempotent operations.
- `app/integrations/wildberries`: WB API client, schemas, retry, rate limiting.
- `app/integrations/ozon`: Ozon API client, schemas, retry, rate limiting.
- `app/workers`: scheduler and sync job.
- root `wb_export_agent.py`, `wb_api.py`, `google_sheets_writer.py`, `models.py`: standalone Wildberries Google Sheets export agent.
- `docs/plan`: separate feature plans, including buyer questions and Ozon reviews automation.
- `.specify/specs/cutter-cabinets`: specification, technical plan, and task list for the planned cutter cabinet web app.
- `cutter-cabinets`: separate TypeScript/Next.js web app for cutter cabinets; keep its package, tests, database schema, and Docker assets independent from the Python Telegram services.
- `tests`: automated tests.

## Commands

- `make install`
- `make lint`
- `make format`
- `make typecheck`
- `make test`
- `make migrate`
- `make run`
- `make docker-up`
- `make docker-down`

## Verification

Before handoff run:

```bash
ruff check .
mypy app
pytest
```

## Deploy Target

WB Reviews and Ozon TTN use the main Compose project. Ozon Reviews uses only `docker-compose.ozon-server.yml` as the separate `marketplace-bots-ozon-reviews` project, with its own `ozon-db`, network, and volume.

## Known Risks

WB and Ozon API payloads can evolve. Unknown fields are tolerated and raw payloads are stored, but endpoint contract changes require client updates. Never merge the Ozon Reviews server Compose file with the main Compose file or reuse WB/TTN Telegram tokens.
