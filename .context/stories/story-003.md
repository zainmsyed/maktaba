# Story 003: Build document upload and storage pipeline

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Allow a user to upload PDF and EPUB files, store them on disk, create document records, and queue initial processing jobs.

## Verification
Upload a PDF and an EPUB through the API and confirm each file is stored, hashed, recorded in the database, and assigned processing jobs.

## Scope — files this story may touch
- Multipart upload endpoint
- File validation for PDF and EPUB
- SHA256 hashing and deterministic storage paths
- Initial metadata extraction fallback to filename
- Job creation for extraction and embedding work

## Out of scope — do not touch
- Library UI
- Reader rendering
- Import flows

## Dependencies
- Story 001
- Story 002

---

## Checklist
- [ ] Add an upload endpoint for PDF and EPUB files
- [ ] Validate file type and reject unsupported formats
- [ ] Save files under the configured data directory
- [ ] Compute and persist file hashes and format metadata
- [ ] Create initial processing job records after upload

---

## Issues

---

## Completion Summary

