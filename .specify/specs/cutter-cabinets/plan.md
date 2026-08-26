# Cutter Cabinets Technical Plan

## Scope

Build a separate Russian-language web application for cutter work cabinets. The first implementation should prioritize Google Sheets read-only sync, cutter/admin authorization, source snapshot plus override storage, the cutter task table, admin sync controls, and tests for the one-way sync invariant.

## Recommended Stack

- TypeScript
- Next.js for UI and API routes
- PostgreSQL
- Prisma or Drizzle for migrations and typed DB access
- Zod for request and source-row validation
- Playwright for E2E tests
- Vitest or Jest for unit and integration tests
- Docker Compose for local PostgreSQL and app startup

This is intentionally separate from the current Python Telegram service. If implemented in this repository, place it under a dedicated folder such as `cutter-cabinets/` with its own package metadata, README, tests, and Docker files.

## Architecture

- `web`: Next.js application with Russian UI, cutter cabinet, admin panel, and API.
- `db`: PostgreSQL with row ownership enforced by server-side authorization and, where practical, RLS policies.
- `source-adapter`: provider boundary for `google` and future `microsoft` spreadsheet reads.
- `sync-worker`: scheduled and manually triggered job that reads allowed tabs, normalizes rows, computes checksums, upserts source snapshots, archives missing rows, and logs per-row errors.
- `auth`: login, logout, temporary password change, admin reset, session cookie, and audit log.

## Data Model

Minimum tables:

- `users`: login, password hash or auth provider id, role, active state, temporary password flag, last login.
- `cutter_profiles`: user binding, display name, source sheet name, active state.
- `source_connections`: provider, spreadsheet id or URL, allowed sheets, sync interval, secret references.
- `source_items`: stable source uid, cutter id, source sheet, source row reference, source payload JSON, source updated at, synced at, archived flag, checksum.
- `item_overrides`: item id, cutter id, field name, JSON value, updated at, updated by, unique item plus field.
- `sync_runs`: source connection, status, started/finished timestamps, inserted/updated/archived/error counters.
- `sync_errors`: sync run, sheet, source uid or row reference, error text, timestamp.
- `audit_log`: actor, action, entity, before/after JSON, timestamp, correlation id.

## Source UID Strategy

Preferred: add a hidden UUID column to each source tab or a technical mapping tab controlled by administrators. Without a stable UID, row reordering and insertion cannot be made fully reliable. If no source UID can be added, implementation must record the residual risk and use a deterministic composite key only as a temporary migration aid.

## Interfaces

Cutter API:

- `GET /api/items`
- `GET /api/items/:id`
- `PATCH /api/items/:id/overrides`
- `DELETE /api/items/:id/overrides`
- `POST /api/items/bulk`

Admin API:

- user and cutter-profile CRUD
- source connection configuration
- `POST /api/admin/sync`
- `GET /api/admin/sync-runs`
- `GET /api/admin/audit`

## UI

- Cutter first screen is the actual task table, not a marketing page.
- Table order mirrors source columns `A:O`.
- Search covers articles, name, shipment number, and request number.
- Filters cover period, status, marketplace, FBO/FBS, archive, and local changes.
- Editing uses a side panel or modal and persists only changed fields.
- Locally changed cells have a restrained indicator and tooltip.
- Last successful sync and source status are visible.
- Admin panel covers users, source settings, manual sync, sync results, errors, and audit.

## Security

- Never write to source spreadsheet APIs from production code.
- Use read-only source credentials where possible.
- Store secrets only in environment variables or managed secret storage.
- Mask secrets in logs and UI.
- Validate ownership on every item and override endpoint.
- Audit login attempts, override changes, resets, admin actions, and sync runs.

## Verification Strategy

- Unit tests for row normalization, checksum, source plus override merge, archive behavior, and access checks.
- Integration tests for sync scenarios: new row, changed row, deleted row, sorted rows, duplicate rows, formula error, and empty fields.
- E2E tests for cutter login, filtering, editing, reset, repeat sync, admin login, and manual sync.
- Static checks: lint, typecheck, tests, and a production build.
- Browser smoke tests at desktop and 360 px mobile widths.

## Risks

- The current repository stack is Python-first, while the requested implementation stack is TypeScript/Next.js.
- Stable source UID requires either changing the spreadsheet or maintaining a technical mapping.
- Real Google credentials are external, so CI must use fixtures and mocked source adapters.
- Supporting both Google Sheets and Microsoft Graph in the first slice increases scope; prefer Google first unless production requires both.
