# Story 010: Add full-text search across notes and highlights

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
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
- [ ] Add FTS-backed keyword search queries on notes and highlights
- [ ] Return unified result objects with source metadata
- [ ] Add a global search UI entry point
- [ ] Render search results with document and location context
- [ ] Open the correct document location when a result is selected

---

## Issues

---

## Completion Summary

