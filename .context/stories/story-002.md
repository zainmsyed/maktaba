# Story 002: Define database schema and backend models

**Status:** in-progress  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Implement the core database schema and SQLModel definitions needed for documents, pages, highlights, notes, jobs, config, embeddings, and graph entities.

## Verification
Start the backend against Postgres and confirm the MVP tables are created with the expected columns and indexes.

## Scope — files this story may touch
- Define models for documents, pages, highlights, notes, jobs, config, embeddings, entities, and triples
- Enable pgvector and full-text search columns/indexes
- Keep schema aligned with the PRD's MVP data design

## Out of scope — do not touch
- Upload processing
- Search queries
- Reader UI

## Dependencies
- Story 001

---

## Checklist
- [x] Add SQLModel model definitions for the MVP tables
- [x] Add startup or migration logic to create tables safely
- [x] Enable the vector extension in Postgres
- [x] Add indexes needed for document lookup, note lookup, jobs, vector search, and FTS
- [x] Verify soft-delete and import fields exist where required

---

## Issues

---

## Completion Summary
- Added SQLModel models for documents, pages, highlights, notes, jobs, config, embeddings, entities, and triples.
- Added startup schema initialization that enables the pgvector extension and creates the MVP tables and indexes safely.
- Added pgvector to the backend dependency set and verified the resulting schema against Postgres.

