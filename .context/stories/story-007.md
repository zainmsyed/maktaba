# Story 007: Persist and render PDF highlights

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
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
- [ ] Capture PDF text selections and map them to page coordinates
- [ ] Save highlights through backend APIs
- [ ] Store normalized geometry and extracted text for each highlight
- [ ] Render saved highlights over the PDF viewer
- [ ] Add delete support for highlights with confirmation

---

## Issues

---

## Completion Summary

