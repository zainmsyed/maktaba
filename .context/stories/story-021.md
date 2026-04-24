# Story 021: Export backups for notes and highlights

**Status:** not-started  
**Created:** 2026-04-24  
**Last accessed:** 2026-04-24  
**Completed:** —

---

## Goal
Provide a basic backup/export path so notes and highlights can be saved outside the database as a portable archive.

## Verification
Run the backup export and confirm it produces an archive containing notes as markdown and highlights as structured data.

## Scope — files this story may touch
- Export notes grouped by document as markdown
- Export highlight data as JSON or similar structured format
- Package exports into a single downloadable or generated archive
- Document the export command or UI entry point

## Out of scope — do not touch
- Cloud backup integrations
- Incremental backup scheduling
- Full document binary export

## Dependencies
- Story 008
- Story 014
- Story 019

---

## Checklist
- [ ] Add a backend export routine for notes and highlights
- [ ] Serialize notes into markdown files grouped by document
- [ ] Serialize highlights into a structured data file
- [ ] Package the export into a single archive
- [ ] Expose the export path through the UI or a documented command

---

## Issues

---

## Completion Summary

