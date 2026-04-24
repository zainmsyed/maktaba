# Story 016: Import Kobo and KOReader highlights

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Import Kobo and KOReader EPUB annotations so external device highlights can render as native CFI-based highlights in Maktaba.

## Verification
Import a Kobo or KOReader sample tied to an existing EPUB and confirm the imported highlights appear visually in the EPUB reader.

## Scope — files this story may touch
- Upload flow for `KoboReader.sqlite`
- Upload flow for zipped KOReader sidecar data
- Parsing and normalization into the EPUB highlight model
- Book matching by title or ISBN
- Import of attached notes when present

## Out of scope — do not touch
- Kindle imports
- PDF positional import mapping
- Automated device sync

## Dependencies
- Story 013
- Story 014

---

## Checklist
- [ ] Add import endpoints and UI for Kobo and KOReader sources
- [ ] Parse CFI-based highlight data from supported export formats
- [ ] Match imported records to existing EPUB documents
- [ ] Save imported highlights and attached notes in the native schema
- [ ] Verify imported highlights render in epub.js like native highlights

---

## Issues

---

## Completion Summary

