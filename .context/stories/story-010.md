# Story 010: Add full-text search across notes and highlights

**Status:** in-progress  
**Created:** 2026-04-24  
**Last accessed:** 2026-05-02  
**Completed:** —

---

## Goal
Implement fast keyword search across note content and highlight text with result metadata and jump-to-location behavior.

## Verification
Search for a known phrase from an existing note and confirm the result list shows the correct document and opens the matching location.

## Scope — files this story may touch
- Full-text search indexes on notes and highlights
- Backend search endpoint for keyword queries
- Search input and results panel in the UI
- Result metadata including document title and page/chapter
- Open-result navigation back into the reader

## Out of scope — do not touch
- Semantic search
- Hybrid ranking
- Advanced filters beyond basic MVP display

## Dependencies
- Story 008

---

## Checklist
- [x] Add FTS-backed keyword search queries on notes and highlights
- [x] Return unified result objects with source metadata
- [x] Add a global search UI entry point
- [x] Render search results with document and location context
- [x] Open the correct document location when a result is selected

---

## Issues

---

## Completion Summary

Implemented full-text search across notes and highlights using the existing PostgreSQL `tsvector` columns (`idx_highlights_fts`, `idx_notes_fts`) and GIN indexes.

**Backend:**
- Added `GET /api/search?q={query}&limit=50` endpoint to `backend/app/main.py`.
- The endpoint uses `plainto_tsquery('english', q)` to search both `highlights.extracted_text` and `notes.content`, joining with `documents` for metadata.
- Returns unified results with `id`, `source_type`, `document_id`, `document_title`, `page_number`, `content`, `highlight_id`, and `rank`.
- Added integration test `test_search_highlights_and_notes` covering highlight hits, note hits, empty query, and no-match scenarios.

**Frontend:**
- Added a global search input to the library page topbar (between nav links and upload controls) with a debounced 250ms search.
- Search results render in a dropdown panel showing source type badge, document title, page number, and a 2-line content snippet.
- Clicking a result navigates to the reader with `?highlight={id}` or `?page={n}` query params.
- The reader page now reads these query params after loading highlights/notes and:
  - For `?highlight=`: scrolls to the highlight, focuses it with a brief outline, and opens the popup note editor.
  - For `?page=`: scrolls to that page.
  - Cleans the query params from the URL after jumping so refreshes don't re-jump.
- Added search-related CSS scoped to the library page style block.

