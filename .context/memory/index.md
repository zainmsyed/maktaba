# File Index

.pi/extensions/vazir-context/helpers.ts — Context injection, init, plan, and consolidation extension
.pi/extensions/vazir-context/index.ts — Context injection, init, plan, and consolidation extension
.pi/extensions/vazir-live-reload.ts — Watches .pi/extensions and triggers Pi to reload when extensions change (live-reload helper)
.pi/extensions/vazir-tracker/chrome.ts — Change tracker integration helpers for Chrome-based debugging
.pi/extensions/vazir-tracker/index.ts — Change tracker: diff, fix, and reset commands for the workspace
.pi/extensions/vazir-tracker/vcs.ts — VCS integration helpers used by the tracker extension
.pi/lib/vazir-helpers.ts — Utility helpers for Pi: story/frontmatter parsing, date helpers, and VCS detection
.pi/skills/vazir-base/SKILL.md — Vazir baseline skill instructions
AGENTS.md — Cross-framework project guidance and working notes (placeholder; needs project metadata)
backend/app/__init__.py — Package marker for backend app (empty)
backend/app/db.py — Database engine, pgvector checks, bootstrap/init helpers, and get_session dependency
backend/app/extract.py — PDF text extraction with PyMuPDF and optional pytesseract OCR fallback
backend/app/main.py — FastAPI application with endpoints for documents, highlights, notes, streaming, and sanitizers
backend/app/models.py — SQLModel ORM definitions and schema (documents, pages, highlights, notes, embeddings, jobs, etc.)
backend/app/uploads.py — Upload persistence, format validation, metadata extraction, deduplication, and job creation
backend/app/worker.py — Background worker to claim and process extract_text jobs and persist Page rows
backend/pyproject.toml — Backend Python project metadata and dependencies
backend/tests/test_document_upload.py — Integration tests for uploads, notes, highlights, and deletion flows
backend/tests/test_extract_worker.py — Tests for extract worker logic, OCR fallback, and failure handling
backend/tests/test_health.py — Health endpoint unit test
backend/tests/test_schema_smoke.py — Schema smoke tests for tables, FK cascade, and critical indexes
docker-compose.yml — Docker Compose for pgvector, backend, worker, and frontend services
frontend/package-lock.json — package-lock.json configuration file
frontend/package.json — package.json configuration file
frontend/src/app.css — Global CSS imports and theme setup (Tailwind + theme.css)
frontend/src/app.d.ts — Type declarations for SvelteKit PageData (apiUrl)
frontend/src/app.html — SvelteKit HTML template
frontend/src/components/NoteEditor.svelte — Reusable note editor with autosave, saving indicator, and focus/save APIs
frontend/src/components/NotePopup.svelte — Accessible popup wrapper with focus trap and header/close control
frontend/src/lib/popup-viewport-guard.ts — Shared viewport-guard utility for keeping popup containers within the viewport boundary
frontend/src/lib/progress.ts — Pure helper for computing reading progress percentage from current page and total pages
frontend/src/lib/theme.css — Paper-style UI tokens and component styles used across the app
frontend/src/pdfjs-dist.d.ts — Minimal TypeScript declarations for pdfjs worker and viewer pieces
frontend/src/routes/+layout.svelte — Root layout importing global styles
frontend/src/routes/+page.server.ts — Loads PUBLIC_API_URL into the page data
frontend/src/routes/+page.svelte — Landing page showing backend health and runtime status
frontend/src/routes/library/[documentId]/+page.server.ts — Server loader: fetch document and jobs, construct fileUrl for reader
frontend/src/routes/library/[documentId]/+page.svelte — Reader page: PDF viewer, highlights, notes sidebar, and editor integration
frontend/src/routes/library/[documentId]/+page.ts — Client-side only flag for the reader route (ssr = false)
frontend/src/routes/library/[documentId]/highlight-api.ts — Client helpers for highlights/notes API calls and payload mapping
frontend/src/routes/library/+page.server.ts — Server loader for the library page (apiUrl)
frontend/src/routes/library/+page.svelte — Library listing and upload UI with polling for jobs
frontend/src/routes/library/demo/+page.svelte — Demo reader with mock highlights and notes for UI preview and testing
frontend/src/test-setup.ts — Vitest/JSDOM test setup: stubs for ResizeObserver, canvas, and cleanup hooks
frontend/svelte.config.js — SvelteKit configuration (node adapter)
frontend/tests/highlight-api.test.ts — Unit tests for highlight-api helpers
frontend/tests/library-page.test.ts — Tests for library UI, upload flow, and polling
frontend/tests/mocks/MockPdfHighlighter.svelte — Mock PdfHighlighter used in frontend tests
frontend/tests/mocks/MockPdfLoader.svelte — Mock PdfLoader harness for tests
frontend/tests/mocks/NotePopupHarness.svelte — Small harness to test NotePopup focus behavior
frontend/tests/mocks/NotePopupTextareaHarness.svelte — Test harness that renders NotePopup with a textarea and buttons to verify focus-trap behavior
frontend/tests/note-editor.test.ts — Component tests for NoteEditor autosave and focus APIs
frontend/tests/progress.test.ts — Unit tests for computeProgressPercent covering edge cases and boundary values
frontend/tests/reader-page.server.test.ts — Server-loader tests for the reader page
frontend/tests/reader-page.test.ts — Integration tests for reader page: highlights, notes autosave, and sidebar interactions
frontend/tests/test-helpers.ts — Shared test helpers and timer utilities for Vitest
frontend/tsconfig.json — TypeScript configuration for the frontend
frontend/vite.config.ts — Vite configuration for the frontend project
package-lock.json — package-lock.json configuration file
package.json — Root package.json
scripts/run-integration-tests.sh — Helper script to run integration tests (local/docker)
docker-compose.local.yml — (undescribed)
docker-compose.prod.yml — (undescribed)
backend/app/paths.py — (undescribed)