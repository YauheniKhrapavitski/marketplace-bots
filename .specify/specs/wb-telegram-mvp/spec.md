# Wildberries Telegram Feedback MVP Specification

## Goal

Create a working Telegram assistant for a Wildberries seller that fetches unanswered feedback, selects a reply from approved templates, shows the feedback card to an authorized operator, and sends the reply only after confirmation.

## User Stories

- As an authorized operator, I can start the bot and see the main menu.
- As an unauthorized Telegram user, I cannot see any review data.
- As an operator, I can connect or replace a WB API token and have it checked against WB.
- As an operator, I can sync unanswered feedback and see each new feedback once.
- As an operator, I can accept, edit, skip, postpone, or ignore a suggested answer for non-five-star feedback.
- As a seller, I can have five-star feedback answered automatically from approved templates during sync.
- As an operator, I can manage templates through Telegram commands.
- As an operator, I can inspect recent processing history and bot status.

## Functional Requirements

- Use PostgreSQL persistence with migrations.
- Store WB API token encrypted.
- Fetch WB feedbacks with unanswered filter through `WildberriesClient`.
- Handle `429`, `500`, `502`, `503`, and `504` with retry/backoff.
- Do not retry `400`, `401`, or `403`.
- Automatically send approved template answers for feedback with rating `5` during synchronization.
- Deduplicate feedback by `wb_account_id + wb_feedback_id`.
- Select templates by product+keyword, product+rating, keyword, rating, then default fallback.
- Preserve feedback action history.
- Restore `sending` feedbacks to `pending` on startup if no successful local send action exists.
- Provide `/health` and `/ready`.
- Run via `docker compose up --build`.

## Non-Goals

- No automatic sending except five-star feedback.
- No LLM text generation.
- No buyer questions or chats.
- No web interface.
- No multi-seller support.
- No billing or CRM.

## Acceptance Criteria

The project is acceptable when lint, typecheck, tests, migrations, README, `.env.example`, and Docker Compose are present, and the app implements the operator-confirmed review reply workflow with template matching and safe WB retries.
