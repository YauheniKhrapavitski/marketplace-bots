# Веб-кабинеты резчиков

Отдельное Next.js/TypeScript-приложение для личных рабочих копий заданий резчиков. Источник данных - Google Sheets, синхронизация строго односторонняя: таблица -> веб-приложение.

## Что уже создано

- Каркас Next.js-приложения с русским кабинетом резчика и админ-экраном.
- PostgreSQL-схема Prisma для пользователей, профилей резчиков, source snapshot, overrides, sync runs, sync errors и audit log.
- Доменная логика нормализации строк `A:O`, checksum, merge `source_snapshot + cutter_overrides`, архивирования удаленных строк.
- Read-only адаптер Google Sheets. Методов записи в исходную таблицу нет.
- Signed cookie login, demo fallback и защищенный admin sync endpoint.
- Unit-тесты для ключевой sync-логики.

## Локальный запуск

```bash
cd cutter-cabinets
copy .env.example .env
npm.cmd install
npm.cmd run prisma:generate
npm.cmd run dev
```

Откройте `http://localhost:3000`.

Демо-вход без БД:

- резчик: `cutter / cutter`
- админ: `admin / admin`

При подключенной БД:

```bash
npm.cmd run prisma:migrate
npm.cmd run seed
```

## Проверки

```bash
npm.cmd run typecheck
npm.cmd test
npm.cmd run build
```

## Настройка Google Sheets

В `.env` задайте:

- `SOURCE_PROVIDER=google`
- `SOURCE_SPREADSHEET_ID=1YMrdjamD90wCFrikA0cjIxpL_3kXpndK0stQjRodamk`
- `GOOGLE_ACCESS_TOKEN` для текущего безопасного read-only адаптера

Для production лучше заменить access token на service-account OAuth flow и выдать учетной записи минимальные права на чтение таблицы.

## Важное ограничение source_uid

Надежная синхронизация требует стабильный `source_uid`. Лучший вариант - скрытая UUID-колонка в источнике или отдельная техническая вкладка соответствий. В текущем доменном коде есть fallback по заявке/отправлению/номеру строки, но он годится только как временная страховка: при сортировке и вставках строк полностью надежным является только стабильный UID.

## Безопасность

- Не добавляйте реальные `.env`, токены и пароли в git.
- Веб-изменения резчика должны храниться только в `ItemOverride`.
- Source adapter не должен получать методов записи в таблицу.
- Все endpoints, работающие с заданиями, должны проверять владельца записи на сервере.
