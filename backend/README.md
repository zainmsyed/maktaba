# Backend

FastAPI backend for Maktaba.

## Local setup with uv

From the repository root:

```bash
cd backend
uv sync
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Useful commands

```bash
# Check the backend health response
uv run python -c "from app.main import health; print(health())"

# Refresh the lockfile after dependency changes
uv lock

# Verify the lockfile is up to date
uv lock --check
```

`uv sync` creates and populates the local `.venv/` directory automatically.
