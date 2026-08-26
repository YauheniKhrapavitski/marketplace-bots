# Constitution

## Product Principles

1. Operator control is mandatory except for the explicitly approved safe case: five-star feedback may be answered automatically from approved templates.
2. Only approved templates produce answers. No LLM-generated copy in MVP.
3. Secrets never appear in source, logs, Telegram messages, health responses, or API output.
4. Telegram handlers call services only; services own repositories and integrations.
5. Wildberries API access is isolated in `WildberriesClient` and guarded by a shared async rate limiter and retries.
6. Callback operations that can send or alter state must be idempotent.
7. Cutter cabinet web app work is separate from Telegram bot workflows and must preserve one-way spreadsheet-to-web synchronization.

## Security Boundaries

- Telegram access is restricted by `TELEGRAM_ADMIN_IDS`.
- WB token is encrypted before persistence using `APP_ENCRYPTION_KEY`.
- Production database is PostgreSQL, not SQLite.
- Health checks do not call WB API and do not reveal configuration values.

## Quality Gates

- `ruff check .`
- `mypy app`
- `pytest`
- Docker Compose must define `bot` and `db`.

## Decision Changes

Any change that expands automatic sending beyond five-star feedback, adds another seller account, or exposes secrets requires an explicit update to the specification and acceptance criteria.

Any change that writes cutter cabinet web edits back to the source spreadsheet requires an explicit replacement of the cutter cabinet specification and acceptance criteria.
