# n8n on VPS

This folder is a separate deployment kit for running n8n 24/7 on an Ubuntu VPS.
It does not affect the MarketPlace Wildberries bots.

## What It Runs

- n8n
- PostgreSQL 16
- Caddy reverse proxy with automatic HTTPS

## VPS Requirements

- Ubuntu 22.04 or 24.04
- 2 GB RAM minimum
- 2 CPU cores recommended
- Public IP address
- Domain or subdomain pointed to the VPS IP

## 1. Connect To VPS

```bash
ssh root@YOUR_SERVER_IP
```

## 2. Install Docker

Upload or copy this folder to the VPS, then run:

```bash
cd n8n-vps
bash scripts/install-docker-ubuntu.sh
```

Log out and log back in after the script finishes.

## 3. Configure DNS

Create an `A` record:

```text
n8n.example.com -> YOUR_SERVER_IP
```

Wait until DNS resolves:

```bash
dig +short n8n.example.com
```

## 4. Create `.env`

```bash
cp .env.example .env
nano .env
```

Generate secrets:

```bash
openssl rand -hex 32
openssl rand -base64 32
```

Put the first value into `N8N_ENCRYPTION_KEY`.
Put the second value into `POSTGRES_PASSWORD`.

## 5. Start n8n

```bash
docker compose up -d
docker compose ps
```

Open:

```text
https://YOUR_DOMAIN
```

Create the first n8n owner account in the browser.

## Useful Commands

```bash
docker compose logs -f n8n
docker compose pull
docker compose up -d
docker compose down
```

## Backup

```bash
bash scripts/backup.sh
```

Backups are written to:

```text
deploy/n8n-vps/backups/
```

## Restore PostgreSQL

```bash
bash scripts/restore-postgres.sh backups/n8n-postgres-YYYYMMDD-HHMMSS.sql
```

## Important

- Do not change `N8N_ENCRYPTION_KEY` after workflows and credentials are created.
- Do not expose PostgreSQL to the internet.
- Keep `.env` private.
- Update regularly with `docker compose pull && docker compose up -d`.

