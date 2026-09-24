#!/bin/sh
set -eu

PROJECT_NAME="marketplace-bots-ozon-reviews"
COMPOSE_FILE="docker-compose.ozon-server.yml"
ENV_FILE=".env.ozon"

if [ ! -f "$ENV_FILE" ]; then
    echo "Missing $ENV_FILE. Copy .env.ozon.example and fill every required value." >&2
    exit 1
fi

require_env_value() {
    key="$1"
    if ! awk -F= -v key="$key" '
        $1 == key {
            value = substr($0, index($0, "=") + 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            if (value != "") found = 1
        }
        END { exit(found ? 0 : 1) }
    ' "$ENV_FILE"; then
        echo "Missing required value: $key in $ENV_FILE" >&2
        exit 1
    fi
}

read_env_value() {
    key="$1"
    file="$2"
    [ -f "$file" ] || return 0
    awk -F= -v key="$key" '
        $1 == key {
            value = substr($0, index($0, "=") + 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
            print value
            exit
        }
    ' "$file"
}

for key in \
    OZON_DB_PASSWORD \
    OZON_TELEGRAM_BOT_TOKEN \
    TELEGRAM_ADMIN_IDS \
    APP_ENCRYPTION_KEY \
    OZON_CLIENT_ID \
    OZON_API_KEY
do
    require_env_value "$key"
done

ozon_token="$(read_env_value OZON_TELEGRAM_BOT_TOKEN "$ENV_FILE")"
wb_token="$(read_env_value TELEGRAM_BOT_TOKEN .env.wb)"
ttn_token="$(read_env_value BOT_TOKEN .env)"

if [ -n "$wb_token" ] && [ "$ozon_token" = "$wb_token" ]; then
    echo "Ozon Reviews must use a Telegram token different from WB Reviews." >&2
    exit 1
fi
if [ -n "$ttn_token" ] && [ "$ozon_token" = "$ttn_token" ]; then
    echo "Ozon Reviews must use a Telegram token different from Ozon TTN." >&2
    exit 1
fi

container_state() {
    docker inspect --format '{{.Id}} {{.State.StartedAt}}' "$1" 2>/dev/null || true
}

WB_CONTAINER="marketplace-bots-wb-bot-1"
TTN_CONTAINER="marketplace-bots-ttn-bot-1"
wb_before="$(container_state "$WB_CONTAINER")"
ttn_before="$(container_state "$TTN_CONTAINER")"

compose() {
    docker compose \
        --project-name "$PROJECT_NAME" \
        --env-file "$ENV_FILE" \
        -f "$COMPOSE_FILE" \
        "$@"
}

compose config --quiet
services="$(compose config --services)"
for forbidden_service in bot wb-bot ttn-bot db
do
    if printf '%s\n' "$services" | grep -Fxq "$forbidden_service"; then
        echo "Safety check failed: Ozon Compose includes $forbidden_service." >&2
        exit 1
    fi
done
compose up -d --build
compose exec -T ozon-db sh -c \
    'PGPASSWORD="$POSTGRES_PASSWORD" psql -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1"'
compose ps

wb_after="$(container_state "$WB_CONTAINER")"
ttn_after="$(container_state "$TTN_CONTAINER")"

if [ "$wb_before" != "$wb_after" ] || [ "$ttn_before" != "$ttn_after" ]; then
    echo "Safety check failed: a WB or TTN container changed during Ozon deployment." >&2
    exit 1
fi

echo "Ozon Reviews deployed. WB and TTN container identities are unchanged."
