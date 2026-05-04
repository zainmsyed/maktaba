# Story 022: Library folders and document search

**Status:** in-progress  
**Created:** 2026-05-03
**Last accessed:** 2026-05-04  
**Completed:** —

---

## Goal
Let users organize documents into folders and find documents quickly from the library search box.

## Verification
- Create a folder, move a document into it, and verify the library view reflects the folder structure.
- Search for a document by title or author from the library search and see it returned in results.

## Scope — files this story may touch
- Backend: add `Folder` model and `document.folder_id` FK; add folder CRUD endpoints; update search endpoint to include documents.
- Frontend: add folder UI in the library (create, rename, delete, drag/move); update search panel to show matching documents; update document grid to filter by selected folder.

## Out of scope — do not touch
- Nested sub-folders (flat folder list only)
- Folder-level permissions or sharing
- Auto-suggested folders based on metadata

## Dependencies
- Story 004
- Story 010

---

## Checklist
- [x] Add `Folder` SQLModel and migration
- [x] Add `folder_id` to `Document` with FK and index
- [x] Add backend endpoints: `GET/POST/PATCH/DELETE /api/folders`
- [x] Add backend endpoint to move a document to a folder
- [x] Extend `/api/search` to return matching documents alongside highlights/notes
- [x] Add folder sidebar/panel in the library UI
- [x] Add "New folder" flow with inline name input
- [x] Add document move-to-folder action (dropdown menu)
- [x] Update library search to render document results and navigate on click
- [x] Show folder breadcrumb or filter chips when inside a folder

---

## Issues

---

## Completion Summary
Added a `Folder` model (`folders` table) and a nullable `folder_id` foreign key on `documents` with a `SET NULL` on-delete policy and an index. The database bootstrap flow now creates the table/column/index via `ensure_folder_columns` for backwards compatibility with existing deployments.

New backend endpoints:
- `GET /api/folders` — list folders
- `POST /api/folders` — create folder
- `PATCH /api/folders/{folder_id}` — rename folder
- `DELETE /api/folders/{folder_id}` — delete folder (documents become uncategorized)
- `PATCH /api/documents/{document_id}` — move document to a folder (or uncategorize)
- `GET /api/documents?folder_id=...` — filter documents by folder; `folder_id=null` returns uncategorized documents

Search (`GET /api/search`) now also queries documents by title and authors via `to_tsvector`, deduplicating document results so each matching document appears once.

Frontend library page now includes:
- A left sidebar listing folders with "All documents" and "Uncategorized" filters
- Inline "New folder" creation with Enter/Escape handling
- Inline folder rename and delete buttons on hover
- A folder chip/breadcrumb shown when a specific folder is selected, with a clear button
- A "Move to folder" dropdown on each document card
- Search results now include `document` source_type and navigate to the reader on click

Schema smoke tests and integration test teardown were updated to include the `folders` table.

