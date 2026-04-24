# Story 006: Add PDF text extraction and OCR fallback

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Extract searchable page text from uploaded PDFs, using OCR only when a page lacks a usable text layer.

## Verification
Process a text PDF and a scanned PDF, then confirm page text is stored for both and OCR is marked only on the scanned pages.

## Scope — files this story may touch
- Per-page PDF text extraction with PyMuPDF
- OCR fallback path using Tesseract for low-text pages
- Persist extracted text and OCR flags in page records
- Hook extraction into the queued processing flow

## Out of scope — do not touch
- Search UI
- Highlight creation
- EPUB extraction

## Dependencies
- Story 002
- Story 003
- Story 005

---

## Checklist
- [ ] Add PDF page extraction logic with PyMuPDF
- [ ] Detect pages that need OCR fallback
- [ ] Add OCR processing for low-text pages
- [ ] Persist page text and OCR flags to the database
- [ ] Connect extraction work to document processing jobs

---

## Issues

---

## Completion Summary

