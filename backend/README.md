# Backend

FastAPI backend for Maktaba.

## Local setup with uv

From the repository root:

```bash
cd backend
uv sync
uv run python -m app.db bootstrap
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`bootstrap` is the explicit database-admin/bootstrap step for a fresh database. It enables `pgvector` and creates the tables. Normal app startup only validates that the extension already exists and then creates any missing tables.

## Useful commands

```bash
# Check the backend health response
uv run python -c "from app.main import health; print(health())"

# Bootstrap a fresh database explicitly
uv run python -m app.db bootstrap

# Validate extension presence and create any missing tables without admin DDL
uv run python -m app.db init

# Run the schema smoke test against a running Postgres database
DATABASE_URL=postgresql+psycopg://app:change-me@localhost:5432/maktaba \
  python -m unittest tests.test_schema_smoke

# Refresh the lockfile after dependency changes
uv lock

# Verify the lockfile is up to date
uv lock --check
```

`uv sync` creates and populates the local `.venv/` directory automatically.
