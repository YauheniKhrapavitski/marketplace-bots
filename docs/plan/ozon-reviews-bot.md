# Ozon Reviews Bot MVP

## Status

Separate planned feature. It will be a new Telegram bot, separate from the
Wildberries bot. Do not implement Ozon reviews inside the existing WB review or WB
buyer questions handlers.

## Goal

Create an Ozon-specific Telegram bot/module for seller review replies. The MVP
fetches Ozon reviews, stores them in separate tables, selects only pre-approved
templates, and sends replies only when the rule is explicitly allowed or after an
operator confirms the answer in the separate Ozon Telegram bot.

## Existing Wildberries Architecture Observed

The current WB reviews workflow is a vertical slice:

- `app/integrations/wildberries/client.py` fetches unanswered/answered reviews and
  sends or edits answers through WB endpoints.
- `app/integrations/wildberries/schemas.py` normalizes WB payloads into a local
  feedback schema and stores raw payloads for contract drift.
- `app/db/models/feedback.py`, `template.py`, and `action.py` own WB review storage,
  templates, and audit history.
- `app/repositories/feedback_repository.py`, `template_repository.py`, and
  `action_repository.py` keep DB access out of Telegram handlers.
- `app/services/sync_service.py`, `matching_service.py`, `rendering_service.py`, and
  `feedback_service.py` own sync, template selection, rendering, and send lifecycle.
- `app/bot/handlers/reviews.py` exposes `/sync`, `/reviews`, manual editing, skip,
  postpone, ignore, and send callbacks.

Ozon should copy this layering pattern, not the WB entities. The Ozon MVP needs its
own models, repositories, service names, action history, template catalog, sync job,
and Telegram bot wiring.

## Separation Rules

- Ozon uses a separate Telegram bot token, for example `OZON_TELEGRAM_BOT_TOKEN`.
- Ozon commands are still Ozon-prefixed for clarity: `/ozon_status`, `/ozon_sync`,
  `/ozon_reviews`, `/ozon_templates`.
- Ozon dispatcher/router setup should be isolated from WB handlers.
- Callback data should be Ozon-prefixed, for example `ozon_review:send:<id>`.
- Database tables should be Ozon-specific: `ozon_accounts`, `ozon_reviews`,
  `ozon_review_templates`, `ozon_review_template_keywords`,
  `ozon_review_template_products`, `ozon_review_actions`, and optionally
  `ozon_review_sync_runs`.
- Ozon template codes must not overlap with WB template codes.
- Ozon review statuses must be local to Ozon; do not reuse WB `feedbacks.status`
  rows or WB actions.
- Shared infrastructure is allowed only when generic: Telegram admin middleware,
  DB session, settings pattern, encryption service, retry/rate-limit helper pattern,
  logging, scheduler, FastAPI health endpoints, Docker Compose.

## Ozon API Facts To Verify Before Implementation

Public Ozon documentation currently identifies these review endpoints:

- `POST /v1/review/list` - get reviews and IDs.
- `POST /v2/review/list` - newer/expanded list filtering mentioned by Ozon news.
- `POST /v1/review/info` - get full information for one review.
- `POST /v1/review/count` - count reviews by statuses.
- `POST /v1/review/comment/create` - leave an official seller comment/reply.
- `POST /v1/review/comment/list` - list approved comments for a review.
- `POST /v1/review/comment/delete` - delete a review comment if needed later.
- `POST /v1/review/change-status` - change review status.

Auth for Seller API uses headers:

- `Client-Id: <seller client id>`
- `Api-Key: <seller api key>`
- `Content-Type: application/json`

Access caveat: Ozon review APIs may require an Ozon subscription or permission such
as review management/Premium-tier access. This must be verified with the seller
account before coding auto-send behavior.

Sources checked on 2026-07-21:

- https://dev.ozon.ru/start/367-Metody-upravleniia-otzyvami-v-Seller-API/
- https://dev.ozon.ru/news/695-Obnovleniia-v-metodakh-dlia-raboty-s-otzyvami-i-voprosami-v-Seller-API/
- https://seller-edu.ozon.ru/api-ozon/how-to-api
- https://pypi.org/project/ozon-api-client/

## Expected Ozon Payload Fields

Exact fields must be confirmed against the live seller account or current schema,
but the local model should be ready for at least:

- Ozon review id.
- SKU/product id/offer id, if present.
- Product name.
- Buyer/display name, if present.
- Rating from 1 to 5.
- Review text.
- Pros and cons, if Ozon returns them separately.
- Published/created timestamp.
- Current Ozon review status.
- Whether an official seller comment already exists.
- Raw payload JSON.

The first client implementation should tolerate unknown fields and preserve raw
payloads, matching the existing WB defensive pattern.

## MVP Behavior

1. `/ozon_sync` seeds Ozon templates, fetches unprocessed/new Ozon reviews, upserts
   them idempotently, selects a candidate template, and leaves risky/unknown reviews
   pending.
2. `/ozon_reviews` shows the next pending Ozon review to the operator with product
   context, selected template text, and action buttons.
3. `/ozon_templates` shows active Ozon templates and their categories/auto-send
   flags.
4. `/ozon_status` reports API connectivity, last successful sync, queue size, and
   answers sent today.
5. Positive 4- and 5-star reviews may be auto-answered only if the user explicitly
   approves that rule for Ozon and Ozon permits replies to that review type.
6. Negative 1-, 2-, and 3-star reviews may be auto-answered only when both rating and
   a known complaint topic match an approved template.
7. Empty, unclear, legal/warranty/refund/delivery/order-specific, abusive, medical,
   safety, or otherwise risky reviews stay pending for manual operator handling.
8. Idempotency: never send a second official comment if an Ozon review already has an
   owner/official comment or a local `answer_sent` action.

## First Templates Needed

Start with Ozon-specific wording, not copied WB text verbatim:

- `ozon_rating_5_positive`: thank-you response for 5-star reviews.
- `ozon_rating_4_positive`: thank-you response for 4-star reviews.
- `ozon_negative_no_text`: ask the buyer to clarify the issue, if Ozon allows replies
  to empty reviews.
- `ozon_packaging_damage`: damaged package/delivery condition; avoid taking blame for
  Ozon logistics unless approved.
- `ozon_wrong_item`: wrong item received; ask for photos/details through Ozon channel
  only if marketplace policy permits.
- `ozon_size_issue`: product did not fit/size mismatch.
- `ozon_installation_difficulty`: installation/use difficulty.
- `ozon_quality_complaint`: product quality complaint.

Each template needs: approved final text, allowed ratings, keywords, optional product
scope, priority, and explicit `auto_send` true/false.

## Missing Data From User

Before implementation, get:

1. Ozon `Client-Id`.
2. Ozon `Api-Key` with review endpoints enabled.
3. Confirmation that the seller account has access to Ozon review-management API
   methods and any required subscription.
4. Separate Telegram bot token for Ozon.
5. Whether 4- and 5-star Ozon reviews may be auto-answered, or must start as manual
   confirmation only.
6. Approved Ozon brand signature and tone of voice.
7. First approved Ozon templates for positive and complaint categories.
8. Product identifiers or offer IDs requiring special templates.
9. Risk policy: which topics must never be auto-answered.
10. Sync cadence and daily/hourly send limits for Ozon.

## Implementation Plan

1. Add Ozon settings: base URL, `Client-Id`, encrypted `Api-Key`, separate Telegram
   bot token, environment label, sync interval/limits if needed.
2. Add `app/integrations/ozon` with schemas, exceptions, rate limiting/retry, and a
   minimal `OzonClient`.
3. Add Ozon Alembic migration and SQLAlchemy models for accounts, reviews, templates,
   template keywords/products, and actions.
4. Add Ozon repositories mirroring the WB repository boundary.
5. Add Ozon template catalog and matching service with explicit `auto_send` support.
6. Add Ozon rendering service using Ozon review context placeholders.
7. Add Ozon sync service with idempotent fetch, template selection, and guarded
   auto-send.
8. Add Ozon manual review service: edit answer, send answer, postpone, ignore.
9. Add separate Ozon Telegram handlers, keyboard, messages, bot commands, and
   optional scheduler job.
10. Add unit tests for Ozon client payload parsing, matching, sync idempotency, no
    duplicate sends, auto-send gates, and manual fallback.
11. Run `ruff check .`, `mypy app`, and `pytest`.

## Acceptance Criteria

- Existing WB `/sync`, `/reviews`, `/templates`, and WB questions commands keep their
  behavior.
- Ozon reviews run through the separate Ozon Telegram bot and Ozon tables only.
- The bot can fetch Ozon reviews and store raw payloads idempotently.
- Approved templates are selected deterministically.
- Unknown or risky reviews remain pending.
- Auto-send happens only for explicitly approved Ozon rules.
- Duplicate Ozon replies are prevented locally and by checking Ozon comment state when
  available.
- Focused tests cover Ozon behavior independently from WB behavior.
