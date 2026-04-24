# Story 008: Add inline notes, autosave, and notes sidebar

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

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
- [ ] Add note creation and update APIs
- [ ] Open an inline note editor from a selected highlight
- [ ] Autosave note content with debounce and saved feedback
- [ ] Add a notes sidebar for the active document
- [ ] Support jumping from a sidebar note to its highlight location

---

## Issues

---

## Completion Summary

