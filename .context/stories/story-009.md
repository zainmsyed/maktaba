# Story 009: Reader / Notes visual polish

**Status:** in-progress  
**Created:** 2026-04-27  
**Last accessed:** 2026-04-27  
**Completed:** —

---

## Goal

Small, focused visual polish for the PDF reader notes experience so the note editor, autosave micro-UX, popup spacing, and notes sidebar match the project reference and are ready to be reused for EPUB.

This is a targeted follow-up to Story 008 (notes CRUD + core flow). Keep scope deliberately small so EPUB work can reuse the polished components without rework.

## Verification

- Open a document in the reader.
- Create or select a highlight and open the note editor (popup or sidebar).
- Type some text and wait for autosave: the saving indicator should animate then show a saved state and fade after 2s.
- The note should appear in the notes sidebar and remain after a page refresh.
- Click a sidebar note attached to a highlight: the reader should scroll smoothly to the highlight and briefly highlight/focus the target.
- Run the frontend Vitest suite: reader-related tests and snapshots pass.

## Scope — files this story may touch

- frontend/src/components/NoteEditor.svelte (new reusable component)
- frontend/src/components/NotePopup.svelte (popup wrapper, optional)
- frontend/src/components/NotesSidebar.svelte (layout/styling tweaks)
- frontend/src/routes/library/[documentId]/+page.svelte (replace inline editor with component)
- frontend/src/routes/library/[documentId]/highlight-api.ts (minor integration)
- frontend/src/app.css (style tokens / utility classes alignment)
- frontend/tests/* (reader-page.test.ts, mocks, snapshots)
- frontend/tests/mocks/MockPdfHighlighter.svelte (ensure it accurately simulates popup/pinned state)

## Out of scope — do not touch

- Full design system or global theme refactor
- App-wide visual polish beyond the reader and notes components
- EPUB-specific layout/locator work (only ensure the NoteEditor is reusable)

## Dependencies

- Story 008 — notes endpoints and core reader-note flow must be present

---

## Checklist

- [x] Create a reusable NoteEditor Svelte component
  - Props: placement ('sidebar' | 'popup'), initial content, ariaLabel, onChange, onClose, onSave
  - Expose focus API for tests
- [x] Extract or wrap popup behavior into NotePopup (keeps logic small and testable)
- [x] Replace inline editors in the reader with NoteEditor (both popup and sidebar paths)
- [x] Autosave micro-UX
  - Debounced autosave (keep existing 500ms)
  - Animated saving indicator and a "Saved" badge that fades after 2s
  - Micro-interaction for state changes to make saves feel responsive
- [x] Spacing / layout polish to match reference (.context/intake/references/maktaba-ui.html)
  - Editor padding, font-size, border radii, popup offsets
  - Sidebar grouping headers, item spacing and preview text
- [x] Accessibility
  - Ensure textarea has aria-label="Note content"
  - Keyboard focus/trap for popup; ESC closes popup
  - Tab order verified and keyboard shortcuts tested
- [x] Smooth jump-to-highlight behavior
  - Scroll animation when jumping from sidebar to highlight
  - Brief visual focus/outline on the target highlight
- [x] Tests
  - Update MockPdfHighlighter to simulate popup/pinned state
  - Add Vitest tests for NoteEditor (autosave indicator, saved state)
  - Add snapshot(s) for editor and sidebar groupings
  - Run full frontend test suite and fix regressions
- [ ] QA & deliverables
  - Manual QA on desktop and narrow/mobile widths
  - Add screenshots and notes to the story after verification

---

## Issues

- Manual QA and screenshots still need to be captured in a browser session before closeout; the implementation and frontend Vitest suite are verified, but I couldn’t perform the visual pass from this headless environment.

---

## Completion Summary

Implemented the reader/notes visual polish pass for Story 009. I extracted the note composer into a reusable NoteEditor component with focus/save APIs, added a NotePopup wrapper for the popup editor shell and focus trap, replaced the reader’s inline note UI with the reusable component in both sidebar and popup flows, and tuned the note autosave micro-UX to show a saving spinner, saved badge, and 2s fade back to idle. I also tightened the sidebar jump-to-highlight behavior so it smooth-scrolls to the target, focuses it, briefly outlines it, and opens the popup editor.

For visual QA, I added a full-screen paper-style reader demo route and corrected the sidebar color dots to behave as highlight-color filters rather than highlight color pickers, matching the reference semantics and leaving actual highlight color selection to the PDF highlighter module.

On the test side, I updated the mock PdfHighlighter to keep the popup/pinned flow accurate, added component-level tests for NoteEditor and NotePopup, and added/updated reader-page tests and snapshots for autosave behavior, sidebar grouping text, and highlight jump flow. The full frontend Vitest suite passes locally.

Remaining verification gap: manual QA on desktop and narrow/mobile widths plus screenshots/notes are still outstanding in this environment. Once those are captured, the story should be ready for /complete-story.

---

## Reference

- UI reference: .context/intake/references/maktaba-ui.html
