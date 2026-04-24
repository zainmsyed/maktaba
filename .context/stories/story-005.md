# Story 005: Deliver the PDF reader shell

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

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
- [ ] Add a reader route for opening a selected document
- [ ] Stream PDF binaries from the backend to the frontend
- [ ] Integrate PDF.js into the reader view
- [ ] Add fit-width, fit-page, and custom zoom controls
- [ ] Add page navigation controls and current page display

---

## Issues

---

## Completion Summary

