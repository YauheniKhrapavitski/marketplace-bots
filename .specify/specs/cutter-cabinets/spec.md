# Cutter Cabinets Web App Specification

## Goal

Create a production-ready Russian-language web application for cutter work cabinets. The app reads assignments from configured personal tabs in the current online spreadsheet and creates an independent working web copy for each cutter.

The core rule is one-way synchronization only: source spreadsheet to web application. Cutter and admin edits made in the web app must never be written back to the source spreadsheet.

## Audience

- Cutters who need a familiar task table close to their current spreadsheet tab.
- Administrators who manage users, spreadsheet-tab bindings, sync runs, and diagnostics.
- Developers who must safely extend the system without mixing it with existing Wildberries/Ozon Telegram workflows.

## User Stories

- As a cutter, I can log in with a username and password and see only my own assignments.
- As a cutter, I can search, filter, sort, and edit my personal web copy without changing the source spreadsheet.
- As a cutter, I can see which cells I changed locally and reset one field or all row overrides back to the current source value.
- As an administrator, I can create, block, reset, and configure users and bind each cutter profile to a source tab.
- As an administrator, I can run sync manually, inspect sync status, and review sync errors.
- As an administrator, I can view a cutter cabinet for diagnostics while keeping all web edits local to the app.

## Functional Requirements

- The source is a configured online spreadsheet with one allowed tab per cutter.
- Initial active cabinets are: Китасов Саша, Лазаревич Андрей, Жулега Паша, Шараев Андрей, Окуневец Никита, Титоров Максим.
- Adding a new cutter must be possible through admin configuration without code changes.
- Only source columns `A:O` are part of the working list. Service columns `P:R` and source formulas are not shown in the UI.
- Authentication uses username and password. Passwords are never stored in plain text.
- Sessions use protected cookies, with secure production settings.
- First login with a temporary password forces password change.
- Admin can reset passwords.
- Failed login attempts are audited and should be temporarily rate-limited after repeated failures.
- The visible item value is computed as local override first, otherwise latest `source_snapshot`.
- Sync stores two layers: immutable latest source copy and per-field cutter overrides.
- Sync is idempotent and works by stable `source_uid`, not by row number alone.
- Deleted source rows are marked archived instead of physically deleted.
- Per-row errors are logged without stopping the rest of the sync.
- Supported source provider is configured with `SOURCE_PROVIDER`. Google Sheets is required for the provided source link; Microsoft Graph support is a future-compatible adapter boundary unless explicitly selected before implementation.
- Cutter API must support list, detail, patch overrides, delete overrides, and bulk actions.
- Admin API must support users, tab bindings, manual sync, sync runs, and audit log.
- Server-side pagination defaults to 50 and caps at 200.
- The UI is Russian, responsive down to 360 px, accessible by labels and visible focus states, and keeps the table close to the current spreadsheet layout.

## Data Fields

The web list mirrors the agreed 15 fields from source columns `A:O`:

- Дата
- Артикул Vinylstudio
- Наименование
- Комментарий по товарам (раскладки)
- Номер отправления Ozon/WB
- Количество
- Склад
- Артикул Wildberries
- Комментарий по отгрузке
- Сделано/Не сделано
- Коэффициент сложности
- Маркетплейс
- Для расчета ФБО или ФБС
- Коробки/Упаковка
- № Заявки

## Non-Goals

- No writing from the web app to the source spreadsheet.
- No reuse of Wildberries review templates, question templates, Ozon review statuses, or Telegram bot commands.
- No generative AI task editing.
- No billing, public marketplace, or multi-tenant SaaS features.
- No real credentials or production data in seed data.

## Acceptance Criteria

- A cutter sees only assignments linked to their own cutter profile; direct access to another cutter's data returns 403 or 404.
- A new row added to a configured cutter tab appears only in that cutter cabinet within the configured sync interval, no later than 5 minutes.
- Cutter edits to status and comments persist as overrides after reload and repeat sync.
- The source spreadsheet remains unchanged after cutter edits.
- A later source update refreshes `source_snapshot` without deleting cutter overrides.
- A row deleted from the source becomes archived and remains discoverable through the Archive filter.
- Repeated sync runs with the same source data do not create duplicates.
- Admin can see sync results, row-level errors, audit events, and last successful sync time.
- The repository contains source code, migrations, seed admin, source adapter, sync worker, UI, tests, Dockerfile, and README for the selected implementation stack before the feature is considered complete.

## Unresolved Questions

- Should this web app live in this repository beside the existing Python Telegram project, or should it be created as a separate TypeScript/Next.js repository?
- Is Google Sheets the only production source provider for the first release?
- Can a stable hidden UUID column be added to the source spreadsheet, or must the app maintain a separate technical mapping table?
- Which deployment target should be used for the web app and PostgreSQL database?
- Which authentication option is preferred: managed Auth/RLS platform such as Supabase, or application-owned password hashing and authorization?
