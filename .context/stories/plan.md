# Project — Plan

**Created:** 2026-04-24  
**Last updated:** 2026-04-27

---

## What we're building
Maktaba is a brand new single-user, self-hosted web app for reading PDFs and EPUBs, capturing highlights and notes, and retrieving those notes later. MVP/v1 follows the PRD's pre-AI roadmap: foundation, PDF-first reading, search, EPUB support, imports, and polish. The launch priority is a smooth desktop/laptop reading experience and a fast highlight → note loop.

## What we're not building (v1 scope)
- AI retrieval, chat, reranking, or multi-agent flows
- Mobile/iPad optimization
- Cover thumbnail extraction for the library
- Multi-user accounts, collaboration, or auth flows
- Citation management, writing/publishing workflows, social features

## Product and technical constraints
- Build from scratch using the PRD stack: SvelteKit frontend, Tailwind CSS, FastAPI backend, SQLModel, Postgres + pgvector, PDF.js, epub.js, Docker Compose
- Desktop/laptop first
- Single-user deployment via Docker with local/self-hosted data ownership
- PDF flow lands first; EPUB is still part of MVP and follows after the PDF core loop is solid

## Delivery strategy
1. Establish the app skeleton, database, and upload pipeline.
2. Ship the PDF reading and note-taking loop first, keeping highlight persistence and popup behavior in a small route-local helper module.
3. Add retrieval foundations: full-text, embeddings, hybrid search.
4. Add EPUB support and external highlight imports.
5. Finish with polish, lifecycle flows, scanning, and backup/export.

## Features
### Feature 1: Foundation and upload
Create the runnable app skeleton, database schema, storage model, upload flow, and library shell.
Stories: 001, 002, 003, 004

### Feature 2: PDF reading and notes
Build the PDF reader, extraction pipeline, persistent highlights, route-local highlight helpers, inline note editing, notes sidebar, and background processing UX.
Stories: 005, 006, 007, 008, 009

### Feature 3: Retrieval
Add full-text search, embeddings, semantic search, hybrid ranking, and result navigation.
Stories: 010, 011, 012

### Feature 4: EPUB and imports
Add EPUB rendering and CFI highlights, then bring in Kindle and Kobo/KOReader import paths plus reading graph basics.
Stories: 013, 014, 015, 016, 017

### Feature 5: Polish and lifecycle
Add themes, shortcuts, reading progress, soft delete, Calibre scan, backup/export, folders, and document search.
Stories: 018, 019, 020, 021, 022

## Story queue
| Story | Title | Status | Blocks |
|---|---|---|---|
| 001 | Bootstrap project scaffold and Docker runtime | Not started | — |
| 002 | Define database schema and backend models | Not started | 001 |
| 003 | Build document upload and storage pipeline | Not started | 001, 002 |
| 004 | Implement library UI and upload flow | Not started | 003 |
| 005 | Deliver the PDF reader shell | Not started | 003, 004 |
| 006 | Add PDF text extraction and OCR fallback | Not started | 002, 003, 005 |
| 007 | Persist and render PDF highlights | Completed | 005, 006 |
| 008 | Add inline notes, autosave, and notes sidebar | Not started | 007 |
| 009 | Surface background job status and retries | Not started | 003, 006, 008 |
| 010 | Add full-text search across notes and highlights | Not started | 008 |
| 011 | Generate embeddings and semantic search | Not started | 002, 006, 008 |
| 012 | Merge hybrid search with temporal boosting | Not started | 010, 011 |
| 013 | Add EPUB ingestion and reader shell | Not started | 003, 004 |
| 014 | Add EPUB highlights and note interactions | Not started | 013, 008 |
| 015 | Import Kindle My Clippings data | Not started | 003, 008 |
| 016 | Import Kobo and KOReader highlights | Not started | 013, 014 |
| 017 | Record reading graph data and timeline queries | Not started | 002, 004, 013 |
| 018 | Polish themes, shortcuts, and reading progress | Not started | 005, 013, 014 |
| 019 | Add document deletion, soft delete, and recovery window behavior | Not started | 004, 008 |
| 020 | Scan Calibre libraries for bulk import | Not started | 003, 013 |
| 021 | Export backups for notes and highlights | Not started | 008, 014, 019 |
| 022 | Library folders and document search | Not started | 004, 010 |

## Replanning log
- 2026-04-24: Initial MVP/v1 plan created from the PRD, reference UI, and user clarifications. Scope includes all pre-AI milestones (M1–M5), with desktop/laptop focus, PDF-first sequencing, EPUB still inside MVP, and thumbnails/mobile excluded.
