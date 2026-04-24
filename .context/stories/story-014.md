# Story 014: Add EPUB highlights and note interactions

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Support text selection, CFI-based highlight persistence, inline note editing, and note sidebar navigation inside EPUBs.

## Verification
Create a highlight in an EPUB, change font size, refresh the page, and confirm the highlight and attached note still resolve correctly.

## Scope — files this story may touch
- EPUB text selection handling
- CFI range storage and extracted text capture
- Highlight rendering in epub.js
- Inline note editor reuse for EPUB highlights
- Sidebar navigation grouped by chapter

## Out of scope — do not touch
- Kobo or KOReader imports
- Cross-book AI features
- Advanced annotation linking

## Dependencies
- Story 013
- Story 008

---

## Checklist
- [ ] Capture EPUB selections as CFI ranges
- [ ] Persist EPUB highlights and extracted text through the backend
- [ ] Re-render saved EPUB highlights after reload and style changes
- [ ] Reuse the inline note editor for EPUB highlights
- [ ] Group EPUB notes by chapter in the sidebar and support jump navigation

---

## Issues

---

## Completion Summary

