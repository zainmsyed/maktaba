# System Rules

## Rules
- Follow existing project conventions.
- Write directly to real project files.
- Ask before changing ambiguous areas.

## Learned Rules
- Use `uv` as the default Python workflow for backend projects: manage dependencies in `pyproject.toml` and `uv.lock`, create the local `.venv` with `uv sync`, and run backend commands with `uv run`.
- When generating `uv.lock` for containerized builds, match the Python minor version used by the Docker image.
- When you want to persist a reusable lesson, use the `/remember` workflow instead of hand-editing `.context/reviews/remembered.md`.
- When adding schema/bootstrap logic, include at least one automated Postgres smoke test for tables, extensions, and indexes.
