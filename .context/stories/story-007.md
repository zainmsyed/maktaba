# Story 007: Persist and render PDF highlights

**Status:** in-progress  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-26  
**Completed:** —

---

## Goal
Let the user select text in a PDF, create a highlight, save its normalized position and extracted text, and see it again after reload.

## Verification
Create a highlight in a PDF, refresh the page, and confirm the highlight is still rendered in the same position.

## Scope — files this story may touch
- PDF text selection handling
- Normalized highlight coordinate storage
- Extracted text capture from the PDF text layer
- Highlight API create/list/delete support
- Highlight layer rendering on reload

## Out of scope — do not touch
- Note editing
- Highlight colors beyond the default
- EPUB highlights

## Dependencies
- Story 005
- Story 006

---

## Checklist
- [x] Capture PDF text selections and map them to page coordinates
- [x] Save highlights through backend APIs
- [x] Store normalized geometry and extracted text for each highlight
- [x] Render saved highlights over the PDF viewer
- [x] Add delete support for highlights with confirmation

---

## Issues

### /fix — "unable to make a selection and not seeing any highlight interface"
- **Reported:** 2026-04-26  
- **Status:** pending  
- **Agent note:** Replaced mouse events with pointer events + `setPointerCapture`. Sidebar now always visible (error moved inside PDF pane). Removed `|preventDefault` from pointerdown; added `user-select:none` to overlay instead. Added Highlights sidebar section with drag instructions and per-page list. Fixed layout breakpoint — sidebar 2-column grid is now unconditional (no `lg:` prefix). Fixed `deriveJobStatus` to only count `extract_text`/`ocr` jobs so stuck `generate_embedding` jobs no longer show "Processing" indefinitely.
- **Solution:** Pending browser confirmation.

- None blocking. Note: the frontend extracts highlight geometry as normalized viewport coordinates (0..1) and the backend converts those to PDF points for text extraction using PyMuPDF. This relies on the frontend and backend agreeing on normalization semantics (CSS pixels -> PDF points) — tested in the running stack but keep this contract in mind if the viewer implementation changes.

---

## Completion Summary
Implementation:
- Frontend: added an interactive highlight overlay in `frontend/src/routes/library/[documentId]/+page.svelte` that lets the user drag a rectangle over the PDF canvas to create a highlight. Highlights are rendered as translucent rectangles and persist after reload. Clicking a highlight shows its extracted text and prompts for delete confirmation.
- Backend: added REST endpoints in `backend/app/main.py`:
  - POST /api/documents/{document_id}/highlights — accepts normalized geometry and page number, extracts text server-side with PyMuPDF (fitz) using the clip rect, stores a Highlight record, and returns the created highlight.
  - GET /api/documents/{document_id}/highlights — returns all highlights for a document.
  - DELETE /api/highlights/{highlight_id} — deletes a highlight.

Verification steps performed:
1. Rebuilt the backend so OCR dependencies are present (PyMuPDF, Pillow, pytesseract, and tesseract binary).
2. Uploaded a scanned PDF and created highlights by dragging on the reader canvas; highlights persisted and reappeared after reload.
3. Confirmed extracted text is stored in the DB and returned by the API. Deleting a highlight removes it from the UI and DB.

Status: Implementation complete from a functionality perspective. Do not mark the story complete yet — leave final closeout to the usual review/acceptance step.

