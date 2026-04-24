# Story 020: Scan Calibre libraries for bulk import

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Allow Maktaba to scan an existing Calibre library folder and import supported EPUB and PDF files with better metadata from `metadata.opf`.

## Verification
Point the app at a Calibre library folder and confirm matching EPUB and PDF files appear in the library with imported metadata.

## Scope — files this story may touch
- Settings input for a Calibre folder path
- Backend scan endpoint or task
- Recursive discovery of EPUB and PDF files
- Optional metadata enrichment from `metadata.opf`
- Safe skipping of already-imported files

## Out of scope — do not touch
- Live filesystem watching
- DRM handling
- Highlight import from Calibre

## Dependencies
- Story 003
- Story 013

---

## Checklist
- [ ] Add configuration input for a Calibre library path
- [ ] Implement a filesystem scan for EPUB and PDF files
- [ ] Read `metadata.opf` sidecars when available
- [ ] Reuse the document import pipeline for discovered files
- [ ] Skip duplicates based on existing file identity rules

---

## Issues

---

## Completion Summary

