#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 backups/n8n-postgres-YYYYMMDD-HHMMSS.sql"
  exit 1
fi

cd "$(dirname "$0")/.."

docker compose exec -T postgres psql \
  -U "${POSTGRES_USER:-n8n}" \
  -d "${POSTGRES_DB:-n8n}" \
  < "$1"

echo "Postgres restore completed."

