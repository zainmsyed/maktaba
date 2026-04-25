# Story 006: Add PDF text extraction and OCR fallback

**Status:** in-progress  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-25  
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
- [x] Add PDF page extraction logic with PyMuPDF
- [x] Detect pages that need OCR fallback
- [x] Add OCR processing for low-text pages
- [x] Persist page text and OCR flags to the database
- [x] Connect extraction work to document processing jobs

---

## Issues
- Runtime dependencies: PyMuPDF (PyMuPDF), Pillow and pytesseract (Python packages), and the Tesseract OCR binary are required to perform OCR. These are optional at import-time in the implementation; however, without these packages and the tesseract binary installed, OCR will not run and scanned PDFs cannot be fully verified.
- Deployment: The worker that processes `extract_text` jobs is provided as `backend/app/worker.py` and must be run as a separate process (e.g. `python -m app.worker` or via `uv run app.worker`) to consume queued jobs. The current Docker image does not automatically start this worker; adding it to docker-compose is a separate step.

---

## Completion Summary
Implementation notes:
- Added per-page extraction logic in `backend/app/extract.py` using PyMuPDF (fitz). The function `extract_text_and_fallback` returns (page_number, text, ocr_used) tuples and will attempt OCR with pytesseract when the PDF text layer is insubstantial.
- Added a worker (`backend/app/worker.py`) which claims pending `extract_text` jobs, runs extraction, persists `Page` rows (setting `extracted_text` and `ocr_used`), and updates the `Job` status to `completed` or `failed` with an error message.

Verification steps to run locally:
1. Ensure system-level Tesseract is installed (if you want OCR): `tesseract --version`.
2. In the backend environment, install Python extras: `pip install PyMuPDF Pillow pytesseract`.
3. Start the backend normally (docker-compose or uvicorn). Upload a text PDF and a scanned PDF via the UI or `POST /api/documents`.
4. Start the worker in a separate terminal: `python -m app.worker` (or `uv run app.worker`). The worker will claim `extract_text` jobs and populate the `pages` table with extracted text and `ocr_used` flags.

Status: Implementation complete from a code perspective. Manual verification requires installing the optional OCR dependencies and running the worker process (see Issues above). Do not mark the story complete yet — follow-up: run the worker and verify extraction + OCR flags for sample PDFs.

