#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p backups
timestamp="$(date +%Y%m%d-%H%M%S)"

docker compose exec -T postgres pg_dump \
  -U "${POSTGRES_USER:-n8n}" \
  -d "${POSTGRES_DB:-n8n}" \
  > "backups/n8n-postgres-${timestamp}.sql"

docker run --rm \
  -v n8n-vps_n8n-data:/data:ro \
  -v "$(pwd)/backups:/backup" \
  alpine tar czf "/backup/n8n-data-${timestamp}.tar.gz" -C /data .

echo "Backup created in ./backups with timestamp ${timestamp}"

