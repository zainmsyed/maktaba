# Deploy Maktaba on Your Server

## One-command install

From the repository root:

```bash
docker compose up -d
```

This starts Postgres/pgvector, bootstraps the database, starts the backend worker, builds/runs the frontend, and serves Maktaba on port `8080` through Caddy.

Open:

```text
http://<server-ip>:8080
```

If port `8080` is already taken, override only the host port:

```bash
APP_PORT=8081 docker compose up -d
```

Then open:

```text
http://<server-ip>:8081
```

## Useful commands

```bash
# Follow logs
docker compose logs -f

# Update after pulling changes
git pull origin main
docker compose up -d --build

# Stop
docker compose down
```

## Optional configuration

No `.env` file is required for the default local-server install. If you want custom settings, copy `.env.example` to `.env` and edit it before running Compose:

```bash
cp .env.example .env
nano .env
```

Common values:

| Variable | Description |
|---|---|
| `DB_PASSWORD` | Optional custom Postgres password. Defaults to a local install password. |
| `PUBLIC_API_URL` | Browser API URL. Default is `/api` for same-origin Caddy routing. |
| `CORS_ORIGINS` | Allowed frontend origins. Default is `*` for the one-command local-server setup. |
| `APP_PORT` | Host port for the web UI. Default is `8080`; set `APP_PORT=8081` if needed. |

## Public domain / HTTPS

For a public domain with automatic HTTPS, edit `Caddyfile` and use the production compose file:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## Architecture

| Service | Role | Exposed |
|---|---|---|
| `postgres` | pgvector database | internal only |
| `db-bootstrap` | One-time schema + extension setup | runs once |
| `backend` | FastAPI API | internal, proxied by Caddy |
| `worker` | Background PDF text extraction | internal only |
| `frontend` | SvelteKit production server | internal, proxied by Caddy |
| `caddy` | Reverse proxy | host `${APP_PORT:-8080}` to container `8080` |

Uploaded documents persist in `./data/`. Database data persists in the Docker volume `pgdata`.
