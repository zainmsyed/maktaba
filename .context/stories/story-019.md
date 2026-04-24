# Story 019: Add document deletion, soft delete, and recovery window behavior

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Make document removal safe by adding confirmation, soft delete semantics, and default hiding of deleted documents while keeping data recoverable during the recovery window.

## Verification
Delete a document from the library and confirm it disappears from the default list while its database row remains marked with `deleted_at`.

## Scope — files this story may touch
- Delete confirmation UI
- Soft delete behavior on documents
- Cascading visibility rules for associated notes and highlights
- Default library filtering to exclude deleted items
- Recovery-window-aware backend behavior

## Out of scope — do not touch
- Permanent purge automation
- Multi-user permissions
- Backup export

## Dependencies
- Story 004
- Story 008

---

## Checklist
- [ ] Add a delete action with explicit confirmation
- [ ] Mark documents as soft deleted instead of removing rows immediately
- [ ] Hide soft-deleted documents from normal library queries
- [ ] Keep related notes and highlights inaccessible through normal UI paths
- [ ] Document the recovery window behavior in the backend and UI copy

---

## Issues

---

## Completion Summary

