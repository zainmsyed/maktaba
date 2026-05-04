# Story 022: Library folders and document search

**Status:** not-started
**Created:** 2026-05-03
**Last accessed:** 2026-05-03
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
- [ ] Add `Folder` SQLModel and migration
- [ ] Add `folder_id` to `Document` with FK and index
- [ ] Add backend endpoints: `GET/POST/PATCH/DELETE /api/folders`
- [ ] Add backend endpoint to move a document to a folder
- [ ] Extend `/api/search` to return matching documents alongside highlights/notes
- [ ] Add folder sidebar/panel in the library UI
- [ ] Add "New folder" flow with inline name input
- [ ] Add document move-to-folder action (context menu or drag)
- [ ] Update library search to render document results and navigate on click
- [ ] Show folder breadcrumb or filter chips when inside a folder

---

## Issues

---

## Completion Summary

