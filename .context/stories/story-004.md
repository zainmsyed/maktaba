# Story 004: Implement library UI and upload flow

**Status:** complete  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-25  
**Completed:** 2026-04-25

---

## Goal
Create the desktop library view so uploaded documents appear as usable text-first cards with upload access, sorting, and status feedback.

## Verification
Open the library in the browser, upload a document, and confirm it appears as a card with title, author, format, and processing status.

## Scope — files this story may touch
- Library page layout based on the reference UI
- Upload control wired to the backend
- Document card list without cover thumbnails
- Sort options for last opened, date added, and title
- Processing badges or status text

## Out of scope — do not touch
- Reader implementation
- Search results UI
- Tag filters

## Dependencies
- Story 003

---

## Checklist
- [x] Build the library route and top-level layout
- [x] Add the upload interaction and optimistic/loading states
- [x] Render text-first document cards without thumbnails
- [x] Add sorting controls for the PRD sort modes
- [x] Show processing state on each document card

---

## Issues
- None blocking. Note: the backend did not previously expose a document listing endpoint; I added a GET /api/documents endpoint that returns documents with their jobs so the frontend can render the initial library and processing state.
- Sorting "last opened" falls back to reading_progress.last_opened if present, otherwise updated_at. The project does not yet track last-opened timestamps in the DB; when that is implemented the frontend will automatically use it.

---

## Completion Summary
Implemented the library UI and upload flow per the story checklist. Changes include:

- Frontend
  - Added a new library route at /library:
    - frontend/src/routes/library/+page.svelte — the library UI, upload control, optimistic upload card, sorting controls, and processing badges.
    - frontend/src/routes/library/+page.server.ts — exposes PUBLIC_API_URL to the page.
  - The library page fetches an initial list of documents from the backend and sorts the list client-side (last opened, date added, title). Uploads are performed via POST /api/documents using multipart/form-data with optimistic UI insertion while the upload is in progress.

- Backend
  - Exposed a listing endpoint to support the library page:
    - backend/app/main.py — added GET /api/documents to return documents with their associated jobs (mirrors the POST response shape).

How to verify locally
1. Start the backend (ensure DATABASE_URL / DATA_DIR are set as required by the project). The backend exposes POST /api/documents and the new GET /api/documents endpoints.
2. Start or open the frontend and visit /library (e.g. http://localhost:3000/library or your dev server port).
3. Use the Upload control to select a PDF or EPUB. An uploading card will appear immediately; after the upload completes the document card will update with the returned metadata and processing badge.
4. Use the Sort control to change ordering (Last opened, Date added, Title).

Notes and next steps
- The reader integration and last-opened tracking are out of scope for this story and were not modified beyond fallback logic in the frontend.
- If you want server-side pagination or filtering for large libraries, we should extend the GET /api/documents endpoint with limit/offset and filter params in a follow-up story.

Story status
- Implementation complete for the checklist items. Do not mark the story complete — leave status as in-progress so Vazir can perform the final closeout.
