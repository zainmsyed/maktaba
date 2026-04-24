# Story 013: Add EPUB ingestion and reader shell

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Bring EPUB into MVP with upload support, a desktop reader shell, chapter navigation, and persisted reading settings.

## Verification
Open an uploaded EPUB and confirm chapter content renders, the table of contents navigates, and reader settings persist after refresh.

## Scope — files this story may touch
- EPUB file ingestion and metadata handling
- epub.js integration in the reader
- Table of contents sidebar or chapter navigation
- Reader settings for font size, family, and line spacing
- Persist per-document reading settings locally

## Out of scope — do not touch
- EPUB highlights
- Kobo/KOReader import
- Mobile responsive tuning

## Dependencies
- Story 003
- Story 004

---

## Checklist
- [ ] Add EPUB reader loading with epub.js
- [ ] Add chapter navigation from EPUB metadata
- [ ] Add reader controls for font size, font family, and line spacing
- [ ] Persist EPUB reader settings per document
- [ ] Ensure EPUB documents open from the library like PDFs

---

## Issues

---

## Completion Summary

