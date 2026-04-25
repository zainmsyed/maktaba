# Story 006: Add PDF text extraction and OCR fallback

**Status:** complete  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-25  
**Completed:** 2026-04-25

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

---

## Completion Summary
Implementation notes:
- Added per-page extraction logic in `backend/app/extract.py` using PyMuPDF (fitz). The function `extract_text_and_fallback` returns (page_number, text, ocr_used) tuples and attempts OCR with pytesseract when the PDF text layer is insubstantial.
- Added a worker (`backend/app/worker.py`) which claims pending `extract_text` jobs, runs extraction, persists `Page` rows (setting `extracted_text` and `ocr_used`), and updates the `Job` status to `completed` or `failed` with an error message.
- The worker now skips non-PDF `extract_text` jobs instead of failing them, which keeps EPUB jobs from blocking the queue.
- OCR runtime dependencies are now baked into the backend image and lockfile: PyMuPDF, Pillow, pytesseract, and the Tesseract OCR binary.
- Added a `worker` service to `docker-compose.yml` so the extraction queue is consumed automatically alongside the backend stack.

Verification performed in the running Docker stack:
- Rebuilt the backend/worker images with the OCR dependencies installed and confirmed the container imports `fitz`, `pytesseract`, and `PIL`, and that `tesseract --version` works.
- Started the new worker service with `docker compose up -d --build worker` and confirmed it stays up and logs `Starting worker loop (extract_text)`.
- Text PDFs already in the library were processed and produced page text with `ocr_used = false` on every page.
- Uploaded `/home/zain/Downloads/PublicWaterMassMailing.pdf` as a scanned PDF, ran the worker after rebuilding the backend image, and confirmed all 8 pages were stored with extracted text and `ocr_used = true`.
- Verified via SQL queries against the `pages` and `jobs` tables that the extract_text jobs completed and the scanned PDF used OCR only on scanned pages.

Manual verification commands used:
1. Rebuild and start the worker service: `docker compose up -d --build worker` (or the full compose stack).
2. Confirm OCR dependencies are present inside the container: `/app/.venv/bin/python -c "import fitz, pytesseract; from PIL import Image"` and `tesseract --version`.
3. Upload the scanned PDF via `POST /api/documents`.
4. Run the worker helper (`python -m app.worker` or `run_once()` in the backend container) to process `extract_text` jobs.
5. Query `pages` for the document to confirm `ocr_used` is true and extracted text is present.

Status: The implementation is functionally verified in the current Docker environment and the queue worker is now wired into docker-compose for automatic processing. The only remaining operational caveat is to ensure the compose stack is kept running in deployment.

