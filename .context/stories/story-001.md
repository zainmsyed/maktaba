# Story 001: Bootstrap project scaffold and Docker runtime

**Status:** in-progress  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

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
- [ ] Create the frontend and backend project folders
- [ ] Add Docker Compose services for frontend, backend, and Postgres
- [ ] Add environment variable wiring for database and data paths
- [ ] Add a backend health endpoint
- [ ] Add a frontend shell route that boots inside Docker

---

## Issues

---

## Completion Summary

