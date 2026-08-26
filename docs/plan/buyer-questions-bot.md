# Buyer Questions Bot MVP

## Status

Separate planned feature. Not part of the current feedback/reviews workflow.

## Goal

Create a separate bot/module for automatic answers to Wildberries buyer questions.
It must not mix question-processing rules, templates, database statuses, or Telegram
commands with the existing feedback/review assistant.

## Separation From Reviews

The current reviews feature handles Wildberries feedbacks/reviews:

- review ratings from 1 to 5;
- review text, pros, cons;
- approved review-answer templates;
- automatic answers for 4- and 5-star reviews;
- manual handling for unclear negative reviews.

The buyer questions feature must handle a different Wildberries entity:

- buyer questions before or after purchase;
- question text and product context;
- question-answer templates;
- automatic answer rules for recognized topics;
- manual handling when the question topic is unclear or risky.

Shared infrastructure may be reused only where it is generic:

- Docker Compose;
- PostgreSQL;
- FastAPI health endpoints;
- Telegram authorization middleware;
- logging and settings patterns;
- Wildberries HTTP client retry/rate-limit helpers.

Feature-specific code should be separate:

- `app/integrations/wildberries/questions_client.py`
- `app/db/models/question.py`
- `app/repositories/question_repository.py`
- `app/repositories/question_template_repository.py`
- `app/services/question_matching_service.py`
- `app/services/question_sync_service.py`
- `app/services/question_template_catalog.py`
- `app/bot/handlers/questions.py`
- `tests/unit/test_question_*`

## MVP Scope

1. Fetch unanswered buyer questions from Wildberries Questions API.
2. Store questions in a separate `questions` table.
3. Select a pre-approved answer template by topic and product context.
4. Automatically send answers only when the topic is confidently recognized.
5. Leave unclear questions pending for manual review in Telegram.
6. Provide Telegram commands separate from reviews:
   - `/questions_status`
   - `/questions_sync`
   - `/questions`
   - `/question_templates`
7. Keep idempotency: never send two answers to the same buyer question.

## Non-Goals For MVP

- No LLM-generated answers.
- No mixing question templates with review templates.
- No automatic answer when the question asks about legal, warranty, refund, delivery,
  or personalized order issues unless an explicit approved template exists.
- No web UI.
- No multi-seller support.

## Required Decisions Before Implementation

1. Confirm the Wildberries Questions API endpoint and payload format for the seller account.
2. Confirm whether the same WB API token has rights for buyer questions.
3. Define the first set of approved question topics and answer templates.
4. Decide whether this runs inside the same Telegram bot with separate commands or as a
   second Telegram bot token.

## First Implementation Plan

1. Add Wildberries questions schemas and client methods.
2. Add question database models and Alembic migration.
3. Add starter question templates and matching rules.
4. Add sync service with idempotent send logic.
5. Add Telegram commands for questions.
6. Add tests for matching, sync idempotency, and unknown-topic manual fallback.
7. Rebuild Docker and verify with `/ready`, `/questions_status`, and a dry sync.

## Acceptance Criteria

- Existing review commands and review auto-answer behavior continue to work unchanged.
- Buyer questions are visible and processed through separate commands.
- Recognized question topics can be answered automatically from approved templates.
- Unrecognized buyer questions remain pending for manual operator action.
- Tests cover review behavior and question behavior independently.
