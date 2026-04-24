# Story 017: Record reading graph data and timeline queries

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Lay the non-AI graph foundation by recording book and reading-session entities so timeline queries such as "what was I reading in March" are possible.

## Verification
Open and close reading sessions across test dates, then run a timeline query and confirm it returns the expected documents for that period.

## Scope — files this story may touch
- Create book entities on document creation
- Record reading session triples on document open and close
- Store highlight-related graph events where useful
- Add a backend query path for timeline-style reading history

## Out of scope — do not touch
- Concept extraction
- AI question answering
- Graph-based concept retrieval

## Dependencies
- Story 002
- Story 004
- Story 013

---

## Checklist
- [ ] Create book entities when documents enter the library
- [ ] Record reading session facts from reader open and close events
- [ ] Store highlight-related timeline facts needed for later retrieval
- [ ] Add a query endpoint for reading activity over a date range
- [ ] Surface a basic timeline result view or debug output for verification

---

## Issues

---

## Completion Summary

