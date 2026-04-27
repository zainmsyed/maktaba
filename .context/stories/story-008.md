# Story 008: Add inline notes, autosave, and notes sidebar

**Status:** complete  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-27  
**Completed:** 2026-04-27

---

## Goal
Complete the core loop by opening an inline note editor from a highlight, autosaving note content, and listing notes in a sidebar that jumps back to the source location.

## Verification
Create a highlight, type a note, wait for autosave, and then click the sidebar entry to jump back to that highlight.

## Scope — files this story may touch
- Inline note editor opened from highlight interaction
- Debounced note autosave with saved indicator
- Attached notes on highlights and standalone document-level notes
- Notes sidebar grouped by page for PDFs
- Jump-to-highlight interaction from sidebar

## Out of scope — do not touch
- Markdown preview polish
- Cross-document search
- EPUB note grouping

## Dependencies
- Story 007

---

## Checklist
- [x] Add note creation and update APIs
- [x] Open an inline note editor from a selected highlight
- [x] Autosave note content with debounce and saved feedback
- [x] Add a notes sidebar for the active document
- [x] Support jumping from a sidebar note to its highlight location

---

## Issues

---

## Completion Summary
Implemented note CRUD endpoints for document notes and highlight-attached notes, returning sidebar-ready note payloads with page metadata and highlight context. Updated the PDF reader to open an inline note editor from highlight interactions, autosave note text with a saved indicator, and surface notes in a grouped sidebar with jump-to-highlight behavior plus a standalone document-note composer. Verified with the full frontend Vitest suite, backend `py_compile`, and the backend health test; the Postgres-gated backend upload/schema tests remain environment-dependent in this container.

