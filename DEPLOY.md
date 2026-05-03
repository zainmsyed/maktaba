# Deploy Maktaba on Your Server

## Quick Start

```bash
# 1. Clone / pull latest
cd /path/to/maktaba
git pull origin scaffold

# 2. Create env file
cp .env.example .env
nano .env          # edit DB_PASSWORD and domain settings

# 3. Create data directory
mkdir -p data

# 4. Deploy
docker compose -f docker-compose.prod.yml up --build -d

# 5. Check logs
docker compose -f docker-compose.prod.yml logs -f
```

## Prerequisites

- Docker + Docker Compose (v2)
- A server with ports 80 and 443 open
- A domain pointed at your server (for HTTPS)

## Configuration

### 1. Environment Variables

Copy `.env.example` to `.env` and set at minimum:

| Variable | Description |
|---|---|
| `DB_PASSWORD` | Strong password for Postgres. **Required.** |
| `PUBLIC_API_URL` | Where the browser calls the API. Use `/api` if same-origin, or `https://yourdomain.com/api` if separate. |
| `CORS_ORIGINS` | Allowed frontend origins. Include your domain(s). |

### 2. Domain / Caddyfile

Edit `Caddyfile` and replace `maktaba.example.com` with your domain:

```
yourdomain.com {
    reverse_proxy frontend:3000
    reverse_proxy /api/* backend:8000
    reverse_proxy /health backend:8000
    encode gzip
}
```

Caddy automatically handles HTTPS via Let's Encrypt.

### 3. First Deploy

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

This builds the frontend production image, bootstraps the database, and starts all services.

### 4. Verify

```bash
# All containers running?
docker compose -f docker-compose.prod.yml ps

# Healthy?
curl https://yourdomain.com/health
```

## Updates

```bash
git pull origin scaffold
docker compose -f docker-compose.prod.yml up --build -d
docker compose -f docker-compose.prod.yml logs -f
```

## Local / HTTP-Only Testing

If you don't have a domain yet, edit `Caddyfile` to use `:80` (no HTTPS):

```
:80 {
    reverse_proxy frontend:3000
    reverse_proxy /api/* backend:8000
    reverse_proxy /health backend:8000
}
```

Then:
```bash
docker compose -f docker-compose.prod.yml up --build -d
```

Access at `http://<server-ip>`.

## Architecture

| Service | Role | Exposed |
|---|---|---|
| `postgres` | pgvector database | internal only |
| `db-bootstrap` | One-time schema + extension setup | runs once |
| `backend` | FastAPI API | internal (proxied by Caddy) |
| `worker` | Background PDF text extraction | internal only |
| `frontend` | SvelteKit (prod build) | internal (proxied by Caddy) |
| `caddy` | Reverse proxy + HTTPS | 80, 443 |

Data (uploaded PDFs, EPUBs) persists in `./data/` on the host.
