# Story 005: Deliver the PDF reader shell

**Status:** complete  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-25  
**Completed:** 2026-04-25

---

## Goal
Ship the first usable PDF reader route with PDF.js, desktop layout, page navigation, and smooth zoom controls.

## Verification
Open an uploaded PDF in the reader and confirm it renders with fit-width by default, supports page navigation, and changes zoom smoothly.

## Scope — files this story may touch
- Reader route and split-pane layout
- PDF.js integration
- Fit-width default plus fit-page and custom zoom
- Basic page navigation controls
- Backend file streaming route for PDFs

## Out of scope — do not touch
- Highlighting
- Notes
- OCR or text extraction

## Dependencies
- Story 003
- Story 004

---

## Checklist
- [x] Add a reader route for opening a selected document
- [x] Stream PDF binaries from the backend to the frontend
- [x] Integrate PDF.js into the reader view
- [x] Add fit-width, fit-page, and custom zoom controls
- [x] Add page navigation controls and current page display

---

## Issues
- None

---

## Completion Summary
- Added a dedicated PDF reader route at `/library/[documentId]` with a desktop split-pane layout, document metadata, status summary, page navigation, fit-width / fit-page / custom zoom controls, and a rendered PDF.js canvas.
- Wired the library cards to open PDF documents in the reader instead of the previous placeholder alert; non-PDF documents now show a disabled “PDF only” state.
- Added a backend streaming endpoint for PDF binaries at `/api/documents/{document_id}/file` and covered it with a regression test that verifies the streamed bytes match the uploaded PDF.
- Added frontend coverage for the reader shell and existing library flow so the route, controls, and upload replacement behavior stay exercised.

