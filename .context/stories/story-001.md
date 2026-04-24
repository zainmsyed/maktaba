# Story 001: Bootstrap project scaffold and Docker runtime

**Status:** complete  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** 2026-04-24

---

## Goal
Create the initial Maktaba app skeleton so the frontend, backend, and Postgres services boot together from Docker Compose.

## Verification
Run `docker compose up --build` and confirm the frontend shell loads and the backend responds on its health route while Postgres passes its healthcheck.

## Scope — files this story may touch
- Create the top-level frontend, backend, and data directory structure from the PRD
- Add Dockerfiles for frontend and backend
- Add `docker-compose.yml` and `.env.example`
- Add minimal FastAPI and SvelteKit app entrypoints

## Out of scope — do not touch
- Real database models
- File uploads
- Reader features

## Dependencies
- 

---

## Checklist
- [x] Create the frontend and backend project folders
- [x] Add Docker Compose services for frontend, backend, and Postgres
- [x] Add environment variable wiring for database and data paths
- [x] Add a backend health endpoint
- [x] Add a frontend shell route that boots inside Docker

---

## Issues

---

## Completion Summary
- Added a minimal SvelteKit frontend shell with a live backend health check.
- Added a FastAPI backend with `/health`, CORS, and startup creation of `/data` subdirectories.
- Switched the backend to `uv` with `pyproject.toml`, `uv.lock`, and a local `.venv` workflow.
- Added Dockerfiles, Docker Compose wiring, an example env file, tracked data directories for Postgres and app storage, and a backend README with local `uv` commands.

