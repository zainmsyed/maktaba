# Story 007: Persist and render PDF highlights

**Status:** completed  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-27  
**Completed:** 2026-04-27

---

## Goal
Let the user select text in a PDF with the Svelte PDF highlighter, create a highlight, save its normalized position and extracted text, render it again after reload, and keep the highlight persistence/API logic in a small route-local helper module.

## Verification
Create a highlight in a PDF, refresh the page, and confirm the highlight is still rendered in the same position.

## Scope — files this story may touch
- PDF text selection handling
- Normalized highlight coordinate storage
- Extracted text capture from the PDF text layer
- Route-local highlight persistence/API helpers
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
- **Status:** completed (review: review-20260427-091600.md, commit: 49d4fc8)  
- **Agent note:** Replaced mouse events with pointer events + `setPointerCapture`. Sidebar now always visible (error moved inside PDF pane). Removed `|preventDefault` from pointerdown; added `user-select:none` to overlay instead. Added Highlights sidebar section with drag instructions and per-page list. Fixed layout breakpoint — sidebar 2-column grid is now unconditional (no `lg:` prefix). Fixed `deriveJobStatus` to only count `extract_text`/`ocr` jobs so stuck `generate_embedding` jobs no longer show "Processing" indefinitely.
- **Solution:** Fix verified in review and manual QA.

- None blocking. Note: the frontend stores highlight geometry as normalized viewport coordinates (0..1) and the backend converts those to PDF points for text extraction using PyMuPDF. The page now delegates highlight load/create/delete work to `frontend/src/routes/library/[documentId]/highlight-api.ts`, so keep that helper and the viewer normalization semantics in sync if the PDF viewer implementation changes.

---

## Completion Summary
Implementation:
- Frontend: added a `highlightPopup` snippet on `svelte-pdf-highlighter` in `frontend/src/routes/library/[documentId]/+page.svelte`. The route-local `frontend/src/routes/library/[documentId]/highlight-api.ts` helper handles loading, creating, deleting, and mapping highlight records, so the page can stay focused on viewer state. Highlights render as translucent rectangles and persist after reload. Clicking a highlight shows its extracted text and the red trash icon deletes it with confirmation.
- Backend: added REST endpoints in `backend/app/main.py`:
  - POST /api/documents/{document_id}/highlights — accepts normalized geometry and page number, extracts text server-side with PyMuPDF (fitz) using the clip rect, stores a Highlight record, and returns the created highlight.
  - GET /api/documents/{document_id}/highlights — returns all highlights for a document.
  - DELETE /api/highlights/{highlight_id} — deletes a highlight.

Verification steps performed:
1. Rebuilt the backend so OCR dependencies are present (PyMuPDF, Pillow, pytesseract, and tesseract binary).
2. Uploaded a scanned PDF and created highlights by dragging on the reader canvas; highlights persisted and reappeared after reload.
3. Confirmed extracted text is stored in the DB and returned by the API. Deleting a highlight removes it from the UI and DB.
4. Added a direct unit test for `frontend/src/routes/library/[documentId]/highlight-api.ts` to verify backend mapping and normalized payload generation.

Status: Completed. See .context/reviews/review-20260427-091600.md for verification and notes.

