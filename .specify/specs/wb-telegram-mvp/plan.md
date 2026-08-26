# Technical Plan

## Architecture

One Python async application starts FastAPI, aiogram polling, and APScheduler. Handlers call services; services call repositories and integrations.

## Data

SQLAlchemy async models define users, WB accounts, feedbacks, templates, rating/keyword/product bindings, actions, and sync runs. Alembic creates the schema and seeds default templates.

## Interfaces

- Telegram commands and callbacks for operator workflows.
- FastAPI `/health` and `/ready`.
- WB API client methods: `ping`, `get_unanswered_feedbacks`, `send_feedback_answer`, `edit_feedback_answer`.

## Dependencies

Pinned Python dependencies live in `pyproject.toml`.

## Risks

- Real WB sandbox credentials are external, so automated tests mock WB HTTP.
- Telegram polling needs a real token, so local non-Docker test runs focus on importability and service behavior.

## Verification

Run `ruff check .`, `mypy app`, and `pytest`.
