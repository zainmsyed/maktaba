# Story 015: Import Kindle My Clippings data

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Import Kindle `My Clippings.txt` into Maktaba as searchable text-based highlights and notes matched to existing books where possible.

## Verification
Upload a sample `My Clippings.txt` file and confirm the parsed highlights and notes import with duplicate entries skipped on reimport.

## Scope — files this story may touch
- Upload and parse Kindle clippings files
- Group entries by book
- Match imported entries to existing documents when possible
- Store Kindle locations and text-only highlight data
- Show an import summary before confirmation

## Out of scope — do not touch
- Visual rendering back into PDF or EPUB pages
- Kobo or KOReader imports
- OCR of image-based imports

## Dependencies
- Story 003
- Story 008

---

## Checklist
- [ ] Add an import endpoint and UI for `My Clippings.txt`
- [ ] Parse highlights and notes from Kindle export format
- [ ] Match parsed books to existing library entries with confirmation support
- [ ] Save imported highlights and notes with Kindle location metadata
- [ ] Deduplicate repeated imports using text and location rules

---

## Issues

---

## Completion Summary

