# Story 003: Build document upload and storage pipeline

**Status:** complete  
**Created:** 2026-04-24
**Last accessed:** 2026-04-25  
**Completed:** 2026-04-25

---

## Goal
Allow a user to upload PDF and EPUB files, store them on disk, create document records, and queue initial processing jobs.

## Verification
Upload a PDF and an EPUB through the API and confirm each file is stored, hashed, recorded in the database, and assigned processing jobs.

## Scope - files this story may touch
- Multipart upload endpoint
- File validation for PDF and EPUB
- SHA256 hashing and deterministic storage paths
- Initial metadata extraction fallback to filename
- Job creation for extraction and embedding work

## Out of scope - do not touch
- Library UI
- Reader rendering
- Import flows

## Dependencies
- Story 001
- Story 002

---

## Checklist
- [x] Add an upload endpoint for PDF and EPUB files
- [x] Validate file type and reject unsupported formats
- [x] Save files under the configured data directory
- [x] Compute and persist file hashes and format metadata
- [x] Create initial processing job records after upload

---

## Issues

---

## Completion Summary
- Added a multipart `POST /api/documents` endpoint that accepts PDF and EPUB uploads, stores them under the configured data directory using SHA256-based deterministic paths, and records the document in Postgres.
- Added lightweight PDF and EPUB metadata extraction with filename fallback, and queued initial `extract_text` and `generate_embedding` job rows for each new upload.
- Added backend integration tests that upload both a PDF and an EPUB through the API and verify storage, hashing, metadata, and queued jobs; the schema smoke test continues to pass.

