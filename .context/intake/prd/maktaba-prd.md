# Product Requirements Document

## Maktaba — Self-Hosted Reading & Note-Taking App

**Version:** 2.3  
**Date:** April 13, 2026  
**Status:** Draft for MVP  
**Author:** Zain

---

## 1. Overview

### 1.1 Purpose

A single-user, self-hosted web application for reading PDFs and EPUBs, capturing highlights and notes, and retrieving knowledge across everything you've read. The core loop: read → highlight → note → retrieve. Nothing else until that loop is fast and satisfying.

### 1.2 Philosophy

- **Notes are first-class.** A highlight without a note is a bookmark. The product exists to capture thought, not just location.
- **One thing done well.** No citation management, no collaboration, no social features. A tool that does one thing and earns daily use.
- **Self-hosted, your data.** Runs on your machine via Docker. No accounts, no cloud sync unless you set it up.
- **Build in sequence.** PDF first, EPUB second, AI retrieval last. Each phase must be useful before the next begins.

### 1.3 Target User

- Solo reader working through nonfiction books, articles, and reference material
- Wants to capture thoughts while reading and find them later
- Values data ownership and simplicity over feature breadth
- Works on desktop/laptop, occasionally accesses remotely via Tailscale

### 1.4 Success Criteria

- Highlight → note saved in under 5 seconds
- Search returns relevant notes in under 500ms
- No required configuration to get started (docker compose up and done)
- Used daily after first week of setup

---

## 2. Competitive Landscape

Understanding what exists clarifies what Maktaba is and isn't trying to be.

### 2.1 The Closest Alternatives

**Readwise Reader** is the most direct comparison. It handles PDFs, EPUBs, web articles, newsletters, and RSS in one place with first-class highlighting and AI chat across your highlights. It recently shipped "Chat with Highlights" — natural language queries across everything you've ever annotated. It's polished, actively developed, and genuinely good. The gap: it's cloud-hosted, costs $7.99/month, your data lives on their servers, and notes are an add-on to a read-later app rather than the core. If data ownership doesn't matter to you, use Readwise.

**Kavita** is the closest self-hosted option — PDF and EPUB reader with highlights, notes, and Obsidian export. Built primarily for manga and comics libraries. No semantic search, no AI retrieval, note-taking is an afterthought.

**Reor** is a local-first AI note-taking app with semantic search, auto-linked notes, and RAG-powered Q&A over your notes via Ollama. Strong retrieval, no document reader built in. You'd write notes in it, not read books in it.

**Atomic** (launched April 2026) is a self-hosted AI knowledge base with semantic search and wiki synthesis across your notes, built in Rust + SQLite. No document reader. Notes-first but no reading layer.

### 2.2 The Gap Maktaba Fills

No tool cleanly combines all three: a good PDF/EPUB *reader*, first-class *note-taking attached to highlights*, and *semantic retrieval* of those notes. Every tool does two of the three. Kavita reads well but doesn't retrieve. Reor retrieves well but doesn't read. Readwise does all three but isn't self-hosted and isn't notes-first.

That gap is what Maktaba exists to fill.

### 2.3 The Open Source Reading Ecosystem

Understanding the broader open source reading ecosystem matters for import compatibility and for the newsletter story:

**KOReader** is open source firmware that runs on Kindle, Kobo, and PocketBook devices. It stores highlights in SQLite with proper CFI positions and has a sync server protocol. The cleanest companion device for Maktaba's self-hosted philosophy. If you run KOReader on a Kobo, you get a fully open pipeline: read on device → sync highlights → import into Maktaba.

**Readest** is an open source cross-platform EPUB and PDF reader with highlights, notes, and KOReader sync. Worth studying their epub.js CFI implementation — they've already solved highlight persistence problems that Maktaba will hit in M4.

**Calibre** is the de facto standard for managing DRM-free ebook libraries — format conversion, metadata, library management. Not a reader but the hub most people use to manage their EPUB collection. Maktaba supports Calibre library folder scanning as an import path.

### 2.4 Recommended Device Stack

For a fully open, self-hosted reading pipeline:

```
DRM-free EPUBs (Calibre library)
  → Read on Kobo with KOReader firmware
  → Highlights stored as CFI in KOReader SQLite
  → Import into Maktaba (M4)
  → Retrieve and synthesize with AI (M6)
```

Kindle is supported (text-only highlights via `My Clippings.txt`) but is a dead end for full integration. Kobo + KOReader is the recommended path for anyone building this stack long-term.

---

## 3. Functional Requirements

### 3.1 Document Management

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| DM-1 | Upload PDF or EPUB via drag-drop or file picker | P0 | Async processing, progress indicator |
| DM-2 | Extract metadata (title, author, date) automatically | P0 | Fallback to filename if extraction fails |
| DM-3 | Library view: grid of document cards (title, author, format badge, last opened) | P0 | Sort by last opened, date added, title |
| DM-4 | Delete document with confirmation (cascade to highlights and notes) | P0 | Soft delete, 30-day recovery |
| DM-5 | Tag documents with custom labels | P1 | Filterable in library, color-coded |
| DM-6 | Track reading progress (current page/chapter, % complete) | P1 | Persist on close, restore on reopen |
| DM-7 | Export document notes as markdown | P2 | For backup or sharing |

### 3.2 PDF Viewer & Highlighting

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| PV-1 | Render PDF with smooth zoom (fit-width default, fit-page, custom) | P0 | PDF.js, hardware-accelerated |
| PV-2 | Click-drag to highlight text on any page | P0 | Store coordinates (x, y, w, h, page) normalized 0–1 |
| PV-3 | Extract text from highlight region via PDF text layer | P0 | OCR fallback if text layer absent |
| PV-4 | Click highlight to open note editor inline (popover, not modal) | P0 | Auto-focus text area, save on close |
| PV-5 | Highlights persist visually across sessions | P0 | Re-render on page load |
| PV-6 | Delete highlight with confirmation | P0 | Cascade delete attached note |
| PV-7 | Color-coded highlights (yellow, green, blue, red) | P1 | User assigns meaning (e.g. green = agree, red = question) |
| PV-8 | Keyboard shortcuts: H = highlight mode, Esc = cancel, arrows = navigate pages | P1 | |

### 3.3 EPUB Viewer & Highlighting

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| EV-1 | Render EPUB with epub.js, paginated or scrolling | P0 | User-selectable in settings |
| EV-2 | Select text to create highlight | P0 | Store as CFI range string |
| EV-3 | Extract text from highlight selection | P0 | Available directly from selection event |
| EV-4 | Click highlight to open note editor inline | P0 | Same interaction as PDF |
| EV-5 | Highlights persist across sessions and font-size changes | P0 | CFI + extracted_text as fallback |
| EV-6 | Font size, font family, line spacing controls | P1 | Persist to localStorage per document |
| EV-7 | Chapter navigation sidebar | P1 | TOC from epub metadata |

### 3.4 Note-Taking

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| NT-1 | Rich text notes attached to highlights (markdown rendered, plain text edited) | P0 | Toggle between edit/preview |
| NT-2 | Standalone notes not attached to a highlight (document-level) | P0 | For chapter summaries, reactions |
| NT-3 | Auto-save notes (debounced 500ms, no manual save button) | P0 | "Saved" micro-indicator fades after 2s |
| NT-4 | Notes sidebar: list all notes for current document, click to jump to location | P0 | Grouped by chapter (EPUB) or page (PDF) |
| NT-5 | Full-text search within all notes across all documents | P0 | Part of global search |
| NT-6 | LaTeX math rendering in notes ($...$ inline, $$...$$ block) | P1 | KaTeX |
| NT-7 | Link notes to other notes ("related to") | P2 | Manual linking, shown as footnotes |

### 3.5 Search & Retrieval

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| SR-1 | Full-text search across all notes and highlight text | P0 | Postgres tsvector, instant results |
| SR-2 | Semantic search: find notes by meaning not just keyword | P0 | pgvector + nomic-embed-text via Ollama |
| SR-3 | Hybrid mode: combine keyword + semantic scores | P0 | Weighted merge, tunable |
| SR-4 | Filter results by document, tag, date range | P1 | Sidebar filters |
| SR-5 | Search results show: note text, document title, chapter/page, date | P0 | Click to jump to location in document |
| SR-6 | "Related notes" — surface semantically similar notes to current highlight | P2 | Post-MVP AI feature |

### 3.6 AI Retrieval (Phase 3 — Post-MVP)

The AI layer is built in three sequential versions. Each must be working and used before the next begins.

**M6 v1 — Basic RAG (ship first)**

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| AI-1 | "Ask my notes" — natural language query, answer grounded in your notes | P1 | Tiered RAG: L1 current doc → L2 cross-library |
| AI-2 | Summarize all notes for a document | P1 | One-click, streamed response |
| AI-3 | Pluggable providers: Ollama (local/GPU), Anthropic, OpenAI | P1 | Unified interface, config in UI |
| AI-4 | Context is always your notes — never raw document text | P1 | You wrote the notes; AI surfaces them |
| AI-5 | Answers include citations: note text, book title, page/chapter | P1 | "Based on your note from Atomic Habits, ch.3..." |
| AI-6 | Temporal query support: "what did I note recently about X?" | P1 | Parse date references, apply temporal boost to retrieval |

**M6 v2 — Reranking (after v1 is proven useful)**

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| AI-7 | LLM reranker: verify top-20 candidates before synthesis | P2 | Small local model (3B) as discriminator |
| AI-8 | Reranker runs as separate Ollama model from synthesizer | P2 | e.g. Phi-3 mini or Qwen 2.5 3B for reranking, 13B for synthesis |
| AI-9 | Note vs highlight distinction: "what did I *think*" prefers notes over highlights | P2 | Metadata filter, not model call |

**M6 v3 — Multi-agent pipeline (after v2 is proven useful)**

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| AI-10 | Query router: classify intent before retrieval (temporal, conceptual, exploratory) | P2 | Rule-based or tiny classifier, <100ms |
| AI-11 | Entity extractor: pull concepts from query to guide graph + vector retrieval | P2 | spaCy NER, no LLM required |
| AI-12 | Parallel query routing and entity extraction | P2 | Both run simultaneously before retrieval starts |
| AI-13 | Knowledge graph queries: "what books covered stoicism?" via graph traversal | P2 | Supplements vector search for structural queries |
| AI-14 | Concept entity extraction from highlights during embedding pipeline | P3 | Automatic, background, uses spaCy |

### 3.7 Async Processing

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| AP-1 | On upload: queue text extraction (immediate) + embedding generation (background) | P0 | FastAPI BackgroundTasks |
| AP-2 | Job status tracked in Postgres jobs table | P0 | Pending, processing, completed, failed |
| AP-3 | SSE notifications to frontend when processing completes | P0 | Auto-update document status badge |
| AP-4 | Manual reprocess button for failed jobs | P1 | Shown on document card if failed |

### 3.8 External Imports

Maktaba is not just for books you read inside it. A meaningful portion of your reading happens on other devices — Kindle, Kobo, physical books annotated elsewhere. Import support brings that existing knowledge in without manual re-entry.

**Amazon Kindle — `My Clippings.txt`**

Every Kindle device generates a plain text file (`My Clippings.txt`) containing all highlights and notes. Amazon has no official API — this file is the only reliable, stable export path. It requires no credentials, no scraping, no third-party service.

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| IM-1 | Upload `My Clippings.txt` via import UI | P1 | Parse all highlights and notes by book |
| IM-2 | Match book title to existing documents in library | P1 | Fuzzy match, prompt user to confirm or skip |
| IM-3 | Import highlights as text-only entries (no position data) | P1 | Store extracted_text + kindle_location, format='kindle' |
| IM-4 | Import attached notes alongside highlights | P1 | Map directly to notes table |
| IM-5 | Deduplicate on reimport (same text + location = skip) | P1 | Avoid duplicates if file uploaded twice |
| IM-6 | Show import summary: X highlights, Y notes, Z books matched | P1 | Before confirming import |

Kindle highlights have locations (e.g. `Location 1234`) not page coordinates. They cannot be rendered visually on the PDF/EPUB viewer — they live as searchable, retrievable text notes attached to a book entry. For the purpose of Maktaba (notes first, retrieval second) this is sufficient.

**Kobo — `KoboReader.sqlite`**

Kobo devices store highlights in a SQLite database accessible via USB. Unlike Kindle, Kobo stores real CFI range strings for EPUB highlights — meaning they can be rendered visually in epub.js, not just stored as text.

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| IM-7 | Upload `KoboReader.sqlite` via import UI | P2 | Available in M4+ after EPUB lands |
| IM-8 | Parse highlights table: text, CFI range, book title, timestamp | P2 | Direct SQLite read in Python |
| IM-9 | Match book to existing EPUB in library by title/ISBN | P2 | Prompt user to confirm or upload book |
| IM-10 | Import as full CFI highlights — render visually in epub.js | P2 | Same as native Maktaba highlights |
| IM-11 | Import attached notes | P2 | Map to notes table |

**KOReader — JSON/SQLite export**

KOReader is open source firmware that runs on Kindle, Kobo, and PocketBook devices. It stores highlights in a sidecar `.sdr` folder alongside each book, in SQLite or JSON format with CFI positions.

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| IM-12 | Import KOReader sidecar `.sdr` folder (zipped) | P2 | Parse highlights.lua or SQLite |
| IM-13 | Map CFI positions to epub.js highlights | P2 | Same pipeline as Kobo import |

**Calibre library scan**

Calibre is the de facto standard for managing DRM-free ebook libraries. Supporting Calibre means users can point Maktaba at their existing library folder and have all their EPUBs appear automatically.

| ID | Requirement | Priority | Notes |
|---|---|---|---|
| IM-14 | Scan a folder path and auto-import all EPUBs and PDFs found | P2 | Config option in settings, not one-time upload |
| IM-15 | Read Calibre `metadata.opf` sidecar files for title/author/ISBN | P2 | Better metadata than extracting from file |

**Import source compatibility matrix**

| Source | Device | Export file | Highlight positions | Priority |
|---|---|---|---|---|
| Kindle (stock firmware) | Kindle | `My Clippings.txt` | Text only (Kindle location) | P1 |
| Kobo (stock firmware) | Kobo | `KoboReader.sqlite` | Full CFI (EPUB only) | P2 |
| KOReader | Kindle, Kobo, PocketBook | `.sdr` sidecar folder | Full CFI (EPUB only) | P2 |
| Calibre library | — | Folder scan | N/A (books only, no highlights) | P2 |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| Metric | Target |
|---|---|
| PDF first page render | < 1 second |
| EPUB chapter render | < 500ms |
| Note auto-save | < 500ms debounce, instant feedback |
| Search (keyword) | < 200ms |
| Search (semantic) | < 500ms |
| Upload confirmation | < 2 seconds (processing continues in background) |

### 4.2 Reliability

- Postgres WAL for durability — no data loss on crash
- PDFs/EPUBs stored with SHA256 hash, verified on read
- Soft deletes: documents recoverable for 30 days
- Embeddings regeneratable from stored text — losing the vector index is not catastrophic

### 4.3 Security

- Single-user, no authentication required
- Network security via Tailscale for remote access
- No outbound calls except Ollama (localhost) and configured cloud LLM APIs
- File storage readable only by app user

### 4.4 Capacity (Single-User)

| Resource | Soft Limit |
|---|---|
| Documents | 5,000 |
| Storage | 50GB |
| Notes per document | 1,000 |
| Concurrent uploads | 3 |

---

## 5. User Interface

### 5.1 Layout — Library View

```
┌─────────────────────────────────────────────────────────┐
│  Maktaba    [Search...]           [Upload]  ⚙️  🌙      │
├─────────────────────────────────────────────────────────┤
│  All  |  Reading  |  Finished  |  [tag: philosophy]     │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ [thumb]  │  │ [thumb]  │  │ [thumb]  │              │
│  │ Title    │  │ Title    │  │ Title    │              │
│  │ Author   │  │ Author   │  │ Author   │              │
│  │ 68% ░░█  │  │ PDF  32p │  │ EPUB     │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Layout — Reader View

```
┌─────────────────────────────────────────────────────────┐
│  ← Library   Thinking Fast and Slow        [Search] ⚙️  │
├────────────────────────┬────────────────────────────────┤
│                        │  [Notes]  [Highlights]         │
│   DOCUMENT VIEWER      │  ──────────────────────────    │
│   (PDF.js or epub.js)  │  Ch.3 — p.47                  │
│                        │  "The availability heuristic   │
│   [Highlight layer]    │   distorts..."                 │
│                        │    └─ This connects to Kahneman │
│                        │       on anchoring. Similar to  │
│                        │       what Taleb argues in...   │
│                        │                                 │
│                        │  Ch.3 — p.51                   │
│                        │  "We are blind to our..."       │
│                        │    └─ [Add note...]             │
└────────────────────────┴────────────────────────────────┘
```

### 5.3 Themes

| Mode | Background | Text | Surfaces |
|---|---|---|---|
| Light | `#ffffff` | `#0f172a` | `#f8fafc` |
| Dark | `#0f172a` | `#f1f5f9` | `#1e293b` |
| Warm (reading) | `#faf6f1` | `#1c1917` | `#f5ede3` |

PDF dark mode: `filter: invert(1) hue-rotate(180deg)` on the canvas only — not the UI.

### 5.4 Key Interactions

| Action | Feedback |
|---|---|
| Upload | Toast: "Processing The Almanack of Naval Ravikant..." |
| Processing complete | Badge updates, toast: "Ready to read" |
| Highlight created | Rectangle pulses once, note popover opens |
| Note saved | Micro-text "Saved" fades after 2s |
| Search | Results appear as you type (debounced 300ms) |
| Job failed | Card badge: "Processing failed · Retry" |

---

## 6. Technical Architecture

### 6.1 Stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | SvelteKit | Fast, minimal, stores are natural for this |
| Styling | Tailwind CSS | Dark mode trivial, no runtime overhead |
| PDF Render | PDF.js (pdfjs-dist) | Standard, extensible highlight layer |
| EPUB Render | epub.js | CFI support, reflowable text |
| Backend | FastAPI | Async native, clean OpenAPI, BackgroundTasks built in |
| ORM | SQLModel | Pydantic + SQLAlchemy, type-safe |
| Queue | FastAPI BackgroundTasks | No Redis, no Celery — sufficient for single user |
| Database | Postgres + pgvector | Search + embeddings in one place |
| Text extract | PyMuPDF + Tesseract | Fast extraction, OCR fallback |
| Embeddings | Ollama (nomic-embed-text) | Local, fast, GPU-accelerated |
| LLM (Phase 3) | Ollama / Anthropic / OpenAI | Pluggable via unified interface |

### 6.2 System Diagram

```
┌─────────────┐      HTTP / SSE      ┌─────────────┐
│  SvelteKit  │ ◄──────────────────► │   FastAPI   │
│  Frontend   │                      │   Backend   │
│  :5173      │                      │   :8000     │
└─────────────┘                      └──────┬──────┘
                                            │
                          ┌─────────────────┼──────────────────┐
                          │                 │                  │
                          ▼                 ▼                  ▼
                    ┌──────────┐     ┌──────────┐      ┌──────────┐
                    │ Postgres │     │  Ollama  │      │    FS    │
                    │+pgvector │     │ :11434   │      │ /data/   │
                    │          │     │          │      │ pdfs/    │
                    │ documents│     │ • embed  │      │ epubs/   │
                    │ pages    │     │ • chat   │      │ thumbs/  │
                    │ highlights     └──────────┘      └──────────┘
                    │ notes    │
                    │ embed.   │
                    │ jobs     │
                    │ config   │
                    └──────────┘
```

### 6.3 Database Schema

```sql
-- Documents (PDFs and EPUBs)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_path TEXT NOT NULL UNIQUE,
    file_hash TEXT NOT NULL,
    format TEXT NOT NULL CHECK (format IN ('pdf', 'epub')),
    title TEXT,
    authors TEXT[],
    publication_date DATE,
    page_count INTEGER,
    cover_path TEXT,
    tags TEXT[],
    reading_progress JSONB,  -- {page: 42} or {cfi: "epubcfi(...)"}
    deleted_at TIMESTAMPTZ,  -- soft delete
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pages (PDF only — text per page for extraction and embedding)
CREATE TABLE pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,
    extracted_text TEXT,
    ocr_used BOOLEAN DEFAULT FALSE,
    thumbnail_path TEXT,
    UNIQUE(document_id, page_number)
);

-- Highlights (PDF, EPUB, and imported Kindle/Kobo)
CREATE TABLE highlights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    format TEXT NOT NULL CHECK (format IN ('pdf', 'epub', 'kindle')),
    -- PDF fields (null for EPUB/Kindle)
    page_number INTEGER,
    x FLOAT, y FLOAT, width FLOAT, height FLOAT,
    -- EPUB/KOReader/Kobo fields (null for PDF/Kindle)
    cfi_range TEXT,
    chapter_title TEXT,
    -- Kindle import fields (null for PDF/EPUB)
    kindle_location TEXT,  -- e.g. "Location 1234"
    import_source TEXT,    -- 'kindle', 'kobo', 'koreader', null for native
    -- Shared
    extracted_text TEXT NOT NULL,  -- always store raw text as fallback
    color TEXT DEFAULT 'yellow' CHECK (color IN ('yellow', 'green', 'blue', 'red')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Notes (attached to highlight or standalone at document level)
CREATE TABLE notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    highlight_id UUID REFERENCES highlights(id) ON DELETE CASCADE, -- null = standalone
    content TEXT NOT NULL,  -- markdown
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Embeddings (pgvector)
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL CHECK (source_type IN ('page', 'highlight', 'note')),
    source_id UUID NOT NULL,
    embedding VECTOR(768),  -- nomic-embed-text-v1.5
    model TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_type, source_id)
);

-- Jobs (async processing status)
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type TEXT NOT NULL CHECK (job_type IN ('extract_text', 'generate_embedding', 'ocr')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Config (LLM providers, user preferences — editable in UI)
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- e.g. key='llm', value={"primary": "ollama", "fallback": "anthropic", "model": "llama3.2"}
-- e.g. key='theme', value={"mode": "warm"}

-- Indexes
CREATE INDEX idx_pages_document ON pages(document_id);
CREATE INDEX idx_highlights_document ON highlights(document_id);
CREATE INDEX idx_notes_document ON notes(document_id);
CREATE INDEX idx_notes_highlight ON notes(highlight_id);
CREATE INDEX idx_embeddings_vector ON embeddings USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_jobs_status ON jobs(status) WHERE status IN ('pending', 'processing');
CREATE INDEX idx_documents_deleted ON documents(deleted_at) WHERE deleted_at IS NULL;

-- Full-text search
ALTER TABLE notes ADD COLUMN fts tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
ALTER TABLE highlights ADD COLUMN fts tsvector GENERATED ALWAYS AS (to_tsvector('english', extracted_text)) STORED;
CREATE INDEX idx_notes_fts ON notes USING gin(fts);
CREATE INDEX idx_highlights_fts ON highlights USING gin(fts);
```

### 6.4 API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/documents` | Upload PDF or EPUB, queue processing |
| GET | `/api/documents` | List documents (paginated, filterable) |
| GET | `/api/documents/{id}` | Get document metadata |
| DELETE | `/api/documents/{id}` | Soft delete |
| GET | `/api/documents/{id}/file` | Stream file binary |
| GET | `/api/documents/{id}/pages` | List pages with extracted text (PDF) |
| POST | `/api/highlights` | Create highlight |
| GET | `/api/documents/{id}/highlights` | List highlights for document |
| PATCH | `/api/highlights/{id}` | Update color |
| DELETE | `/api/highlights/{id}` | Delete highlight + note |
| POST | `/api/notes` | Create note |
| PATCH | `/api/notes/{id}` | Update note content |
| DELETE | `/api/notes/{id}` | Delete note |
| GET | `/api/search?q=...&mode=hybrid` | Search notes + highlights |
| GET | `/api/jobs/{id}/events` | SSE stream for job status |
| POST | `/api/import/kindle` | Upload and parse `My Clippings.txt` |
| POST | `/api/import/kobo` | Upload and parse `KoboReader.sqlite` |
| POST | `/api/import/koreader` | Upload and parse KOReader `.sdr` zip |
| POST | `/api/import/scan` | Trigger folder scan for Calibre library |
| GET | `/api/config` | Get app config |
| POST | `/api/config` | Update app config |

### 6.5 Text Extraction Pipeline

```
Upload file
  │
  ├─ PDF
  │    → PyMuPDF: extract text per page
  │    → if page_text < 50 chars:
  │         pdf2image → Tesseract OCR
  │    → store in pages table (ocr_used=true if fallback)
  │    → generate thumbnail per page
  │    → queue embedding per page + per highlight as created
  │
  └─ EPUB
       → unzip → parse HTML chapters with BeautifulSoup
       → extract text per chapter
       → store in pages table (page_number = chapter index)
       → queue embedding per chapter
```

### 6.6 Search Pipeline

```
Query: "what did I think about heuristics"
  │
  ├─ Keyword: tsvector match on notes.fts + highlights.fts
  │    → ts_rank_cd scores
  │
  └─ Semantic: embed query → cosine similarity on embeddings table
       → top-k results with scores
  │
  └─ Merge: weighted combination (0.4 keyword + 0.6 semantic)
       → return unified ranked results with source metadata
```

---

## 7. Technical Decisions & Reasoning

### 7.1 Why RAG and Not Full-Context

A natural question when adding AI retrieval: why not just send all your notes to the LLM every time? For cloud models with large context windows (Claude, GPT-4) this is actually a viable approach at personal scale — a few hundred notes fit comfortably, retrieval failure is impossible, and implementation is trivial.

But Maktaba targets local models via Ollama as the primary path. Local models (Llama 3.2, Mistral, Qwen) typically have 8k–32k token context windows, and performance degrades as context grows — first token latency increases significantly with longer inputs. Dumping all notes into every query becomes impractical once you have more than a handful of books annotated.

RAG (Retrieval-Augmented Generation) solves this by adding a retrieval step before generation:

```
User query
  → retrieve top-k relevant notes via hybrid search
  → format retrieved notes as context (fits in local model window)
  → LLM generates answer grounded in those notes
  → return answer with source citations
```

The tradeoff: retrieval can fail. If the right note isn't in the top-k results, the answer will be incomplete or wrong — and the user won't necessarily know. This is the core limitation of RAG and why retrieval quality matters so much.

### 7.2 Search and RAG Share the Same Foundation

This is the key architectural insight: the hybrid search built in M3 is not separate from the AI retrieval built in M6. They use the same underlying system.

```
M3 Search (returns notes to the user)
  → tsvector keyword match
  → pgvector semantic match
  → weighted merge → ranked note list → displayed in UI

M6 RAG (returns a synthesized answer)
  → same tsvector keyword match
  → same pgvector semantic match
  → same weighted merge → top-k notes → injected into LLM prompt → answer
```

M6 is M3 plus one step: format the results as an LLM prompt instead of displaying them directly. This means improving search quality in M3 directly improves AI answer quality in M6. They are the same problem.

### 7.3 Why Hybrid Search (Keyword + Semantic)

Neither approach alone is sufficient:

| | Keyword (tsvector) | Semantic (pgvector) |
|---|---|---|
| Strength | Exact matches, fast, deterministic | Finds meaning, handles synonyms and paraphrasing |
| Weakness | Misses synonyms, paraphrasing | Can miss exact terms, slower, less explainable |
| Best for | "Show me notes with 'availability heuristic'" | "What did I think about mental shortcuts?" |

Since you wrote your own notes, you often know the exact words you used — keyword search is underrated here. But semantic search catches the cases where you remember the concept but not the phrasing. Hybrid combines both with a weighted merge (default: 0.4 keyword + 0.6 semantic, tunable).

### 7.4 Why Not Fine-Tuning

Fine-tuning bakes knowledge into model weights. It sounds appealing but is wrong for this use case:

- Fine-tuned models hallucinate trained facts confidently — worse than RAG for factual retrieval
- Every new note would require retraining
- Fine-tuning teaches style and behavior, not retrievable facts
- Significant compute and complexity overhead

RAG keeps your notes as source-of-truth data, not baked into weights. Answers can always be traced back to the specific note that generated them.

### 7.5 Context Window Budget for RAG (Local Models)

When building the RAG prompt, the context must fit within the local model's window. A safe budget:

```
Total context window: ~8,000 tokens (conservative for 7B models)
  - System prompt:        ~200 tokens
  - Retrieved notes:    ~5,000 tokens  (top 8-10 notes at ~500 tokens each)
  - User query:           ~100 tokens
  - Response buffer:    ~2,700 tokens
```

At ~500 tokens per note (roughly 350 words), 8–10 notes is a comfortable retrieval target. If using a cloud model as fallback (Anthropic, OpenAI), the budget expands significantly and more notes can be included.

### 7.6 Tiered Retrieval (Inspired by MemPalace)

Flat RAG treats all notes equally — a note from yesterday competes with one from two years ago on pure vector similarity. A tiered approach prioritizes context that is naturally more relevant based on where you are right now, before falling back to broader search.

Maktaba adopts a lightweight four-layer model:

```
L0 — Current document (always available, no retrieval needed)
     The book you're reading right now. Its notes are loaded on demand
     directly from the notes sidebar. No search required.

L1 — All notes from the current document
     Searched first when you query. High relevance because you're
     actively reading this book.

L2 — Semantically similar notes from other documents
     Hybrid search across your full library. Retrieved when L1
     doesn't surface enough relevant context (top-k < threshold).

L3 — Deep search (all notes, lower similarity threshold)
     Fallback for broad or exploratory queries like "what have I
     ever thought about habit formation?"
```

In practice for the RAG prompt assembly:

```python
def build_rag_context(query, document_id, max_tokens=5000):
    # L1: current document notes first
    l1_notes = search_notes(query, document_id=document_id, limit=5)

    # L2: cross-library if L1 is thin
    if token_count(l1_notes) < max_tokens * 0.5:
        l2_notes = search_notes(query, exclude_document=document_id, limit=5)
    else:
        l2_notes = []

    return merge_and_truncate(l1_notes + l2_notes, max_tokens)
```

This is not a major architectural addition — it's a retrieval ordering decision on top of the existing hybrid search. It means answers about your current book are grounded first in what you've thought about that book, with broader context filling in when needed.

### 7.7 Temporal Boosting

Vanilla semantic search is timeless — a note from three years ago scores identically to one from last week if the embedding similarity is the same. Temporal boosting adds recency as an explicit scoring signal.

Borrowed and adapted from MemPalace's Hybrid v2 architecture, which improved benchmark recall from 97.8% to 98.4% with this single addition.

**Two modes:**

**Explicit temporal** — user query contains a date reference ("what did I note recently about X", "what was I reading in March"). Parse the reference, calculate a target date, apply a strong boost (up to 40%) to notes near that date:

```python
temporal_boost = max(0.0, 0.40 * (1.0 - days_diff / window_days))
fused_score = semantic_distance - keyword_boost - temporal_boost
```

**Implicit recency bias** — no date reference in query. Apply a mild decay (10%) as a tiebreaker between semantically similar notes. Recent thinking on a topic is generally more relevant than old thinking without explicit override.

**Implementation timing:** Add to M3 alongside baseline hybrid search. It's arithmetic on a timestamp you already store — no extra queries, no model calls, highest ROI improvement in the list.

**One Maktaba-specific nuance:** use `highlight.created_at` not `note.created_at` as the timestamp, since notes are sometimes written well after the highlight. The highlight date is closer to "when you encountered this idea."

### 7.8 LLM Reranking

Hybrid search retrieves candidates by similarity — notes *about* the same topic as your query. But similarity isn't the same as relevance. Reranking adds a verification step: a small, fast model judges each candidate and asks "does this actually address the question?"

MemPalace's benchmark shows this step moves recall from 99.4% to 100%. For a personal knowledge tool where trust matters, the difference between "usually right" and "reliably right" is significant.

**Architecture:**

```
Hybrid search → top 20 candidates
      │
      ▼
Reranker (small local model — Phi-3 mini or Qwen 2.5 3B via Ollama)
Prompt: "Query: {query}
         Passage: {note_text}
         Does this passage directly answer the query? yes or no."
      │
      ▼
Filter to "yes" results (typically 5-10 remain)
      │
      ▼
Synthesizer (main 7B/13B model) generates answer from verified context
```

**Why split into two models:** Running a 3B reranker 20 times is much cheaper than running a 13B model 20 times. Memory bandwidth is the GPU bottleneck — a 3B model fits in faster cache tiers. The small model handles discrimination cheaply; the large model synthesizes once, with cleaner context. Result is faster and more accurate than either alone.

**Estimated latency on GPU:**

| Step | Model | Time |
|---|---|---|
| Hybrid retrieval | SQL only | <200ms |
| Reranking (20 candidates) | 3B model | ~1-2s |
| Synthesis | 7B-13B model | ~3-5s |
| **Total** | | **~5-8s** |

**Implementation timing:** M6 v2, after basic RAG (v1) is working and proven useful. Don't build before you have real query data to validate it against.

### 7.9 Knowledge Graph for Temporal Facts

Vector search answers "find me notes about X." It cannot answer "what books did I read that covered both stoicism and decision-making?" or "when did I first encounter loss aversion?" or "show me everything I read in Q1." These are structural and temporal queries — they need a graph.

Maktaba adds a lightweight knowledge graph alongside the vector store, stored in Postgres (no separate database). Entities are books, concepts, authors, and themes. Triples are time-bounded facts: subject → predicate → object, with valid_from and valid_to timestamps.

**Schema addition to Postgres:**

```sql
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('book', 'concept', 'author', 'theme')),
    properties JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE triples (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id UUID REFERENCES entities(id),
    predicate TEXT NOT NULL,  -- 'read', 'highlighted', 'covers', 'related_to'
    object_id UUID REFERENCES entities(id),
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,         -- null = still true
    source_note_id UUID REFERENCES notes(id),
    confidence FLOAT DEFAULT 1.0
);

CREATE INDEX idx_triples_subject ON triples(subject_id);
CREATE INDEX idx_triples_object ON triples(object_id);
CREATE INDEX idx_triples_predicate ON triples(predicate);
```

**Where entities come from — in sequence:**

Phase 1 (M4, automatic, no ML): Book entities created on upload. Reading session triples created automatically when you open/close a document:

```python
# On upload
entity = entities.insert(type='book', name=document.title)

# On open/close
triples.insert(subject='user', predicate='read',
               object=book_entity_id,
               valid_from=first_opened,
               valid_to=None)  # updated on close

# On highlight creation
triples.insert(subject='user', predicate='highlighted',
               object=book_entity_id,
               valid_from=highlight.created_at)
```

Phase 2 (M6 v3, background NLP): Concept entities extracted from highlight text using spaCy NER during the embedding pipeline. "loss aversion", "habit loops", "stoicism" become queryable nodes automatically.

**Query types unlocked:**

| Query | Mechanism |
|---|---|
| "What was I reading in March?" | Temporal filter on reading triples |
| "Which books did I highlight most?" | Aggregate COUNT on highlighted triples |
| "What books covered stoicism?" | Graph traversal: books → covers → stoicism |
| "When did I first encounter loss aversion?" | Timeline query: earliest triple where object = entity |
| "Show books connected to Atomic Habits" | Shared concept nodes via graph |

**Implementation timing:** Book and session triples in M4 (automatic, zero ML cost). Concept extraction in M6 v3 (requires spaCy in the embedding pipeline).

### 7.10 Multi-Agent Pipeline

Rather than one large model doing everything, the full M6 v3 pipeline uses specialized small models for each step — each doing one narrow task well. The key insight for local inference: running a 3B model twice is much cheaper than running a 13B model once, because memory bandwidth is the bottleneck.

**Full pipeline architecture:**

```
User query
    │
    ├──────────────────────────────────┐
    ▼                                  ▼
Query Router                    Entity Extractor
(rule-based or 1B model)        (spaCy NER — no LLM)
intent: temporal/conceptual/    concepts: ["stoicism",
        exploratory              "decision-making"]
    │                                  │
    └──────────┬───────────────────────┘
               │  (run in parallel, ~100ms total)
               ▼
         Retriever
         (SQL only — hybrid search + graph lookup)
         top-20 candidates
               │
               ▼
         Reranker
         (3B model — Phi-3 mini / Qwen 2.5 3B)
         top-5 verified relevant notes
               │
               ▼
         Synthesizer
         (7B-13B model — Llama 3.1 / Mistral)
         answer with citations
```

**Agent responsibilities:**

| Agent | Implementation | Task | Latency |
|---|---|---|---|
| Query router | Rules + regex | Classify intent, extract date refs | <50ms |
| Entity extractor | spaCy | Extract concepts from query | <50ms |
| Retriever | SQL (pgvector + tsvector) | Fetch top-20 candidates | <200ms |
| Reranker | 3B Ollama model | Filter to verified-relevant | ~1-2s |
| Synthesizer | 7B-13B Ollama model | Generate answer with citations | ~3-5s |

Router and entity extractor run in parallel. Retriever can start fetching while extraction finishes. Total pipeline: ~5-8 seconds on GPU — acceptable for a feature where users expect to wait.

**On fine-tuning small models**

Task-specific fine-tuning of the reranker is worth considering after the pipeline is working with off-the-shelf models. A 1B model fine-tuned specifically on relevance judgment ("is this note relevant to this query?") would outperform a general 7B model at that specific task and run significantly faster. Training data is synthetic — generate thousands of query/note/relevant pairs automatically from your own notes. This is a Phase 4 optimization, not a foundation, and excellent newsletter material once you have real usage data to train on.

**Build sequence (important):**

```
M6 v1: Single model, basic RAG, tiered retrieval — ship and use it
M6 v2: Add 3B reranker — measure whether answers actually improve
M6 v3: Add query router + entity extractor + knowledge graph queries
Phase 4: Fine-tune reranker on your own query data if needed
```

Do not build v3 before v1 is working. The architecture is correct — the sequencing is what makes it finishable.

---

## 8. Deployment

### 8.1 Docker Compose

```yaml
version: '3.8'
services:
  postgres:
    image: pgvector/pgvector:pg16
    volumes:
      - ./data/postgres:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: maktaba
      POSTGRES_USER: app
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d maktaba"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    volumes:
      - ./data:/data
    environment:
      DATABASE_URL: postgresql://app:${DB_PASSWORD}@postgres/maktaba
      OLLAMA_URL: http://host.docker.internal:11434
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      DATA_DIR: /data
      MAX_UPLOAD_SIZE_MB: 100
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      PUBLIC_API_URL: http://localhost:8000
```

### 8.2 Environment Variables

| Variable | Default | Required |
|---|---|---|
| `DB_PASSWORD` | — | Yes |
| `ANTHROPIC_API_KEY` | — | No |
| `OPENAI_API_KEY` | — | No |
| `OLLAMA_URL` | `http://localhost:11434` | No |
| `DATA_DIR` | `/data` | No |
| `MAX_UPLOAD_SIZE_MB` | `100` | No |

### 8.3 Folder Structure

```
maktaba/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routes
│   │   ├── models/        # SQLModel schemas
│   │   ├── services/
│   │   │   ├── extraction.py   # PyMuPDF + Tesseract
│   │   │   ├── embeddings.py   # Ollama embed
│   │   │   ├── search.py       # Hybrid search
│   │   │   ├── imports.py      # Kindle/Kobo/KOReader/Calibre parsers
│   │   │   └── llm.py          # Pluggable LLM (Phase 3)
│   │   └── main.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   │   ├── components/
│   │   │   │   ├── PDFViewer.svelte
│   │   │   │   ├── EPUBViewer.svelte
│   │   │   │   ├── HighlightLayer.svelte
│   │   │   │   ├── NoteEditor.svelte
│   │   │   │   └── SearchPanel.svelte
│   │   │   ├── stores/        # documents, highlights, theme
│   │   │   └── api.ts
│   │   └── routes/
│   │       ├── +page.svelte        # Library
│   │       └── read/[id]/+page.svelte  # Reader
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 9. Milestones

| Phase | Duration | Deliverables | Done When |
|---|---|---|---|
| **M1: Foundation** | Week 1 | Docker setup, Postgres schema, FastAPI scaffold, SvelteKit shell, file upload | Files upload, appear in library |
| **M2: PDF Reader** | Week 2–3 | PDF.js viewer, text extraction, OCR fallback, highlight layer, note editor, auto-save, Kindle `My Clippings.txt` import | You read a real chapter and take notes; old Kindle highlights are searchable |
| **M3: Search** | Week 4 | pgvector setup, embedding pipeline, hybrid search UI with temporal boosting, results with jump-to-location | You find a note from memory using a keyword or date reference |
| **M4: EPUB + Graph** | Week 5–6 | epub.js viewer, CFI-based highlights, same note system, Kobo/KOReader import, knowledge graph (book + reading session triples) | You read an EPUB, Kobo highlights render visually, "what was I reading in March?" works |
| **M5: Polish** | Week 7 | Dark/warm themes, keyboard shortcuts, reading progress, soft delete, Calibre folder scan, backup script | You'd show this to someone |
| **M6 v1: Basic RAG** | Week 8–9 | Tiered retrieval (L1/L2/L3), single model synthesis, citations, "ask my notes" UI, temporal queries | You answer a question using your own notes |
| **M6 v2: Reranking** | Week 10 | 3B reranker model, two-model pipeline, note vs highlight distinction in retrieval | Answers are more reliable; fewer irrelevant results |
| **M6 v3: Multi-agent** | Week 11+ | Query router, spaCy entity extractor, parallel pipeline, knowledge graph queries, concept entity extraction | "What books covered stoicism?" answered by graph traversal |

---

## 10. Open Questions

1. **Cover images:** Extract from EPUB metadata (usually included). PDF covers require rendering page 1 as image — worth doing for library aesthetics?
2. **Mobile:** Reading on iPad or phone? epub.js handles reflow well. PDF on mobile is painful. Defer until M5 feedback.
3. **Backup:** Manual export as ZIP (notes as markdown, highlights as JSON) is enough for MVP. Rclone to B2 can be a later config option.
4. **Offline:** Should the app work with no internet? Ollama is already local. Cloud LLM fallback requires connectivity — clearly document this.
5. **E-ink device:** Kobo + KOReader is the recommended companion device for a fully open reading stack. Kindle import (text-only) is supported from day one, but Kobo enables full CFI highlight sync in M4. Worth deciding before M4 begins.
6. **Kindle import edge cases:** `My Clippings.txt` has a 10% highlight limit per book enforced by Amazon on older firmware — some highlights may be silently truncated on the device before export. Document this limitation clearly in the import UI.

---

## 11. What This Is Not

To keep scope honest:

- Not a citation manager (no BibTeX, no Zotero integration)
- Not a collaboration tool (single user, always)
- Not a read-later service (Instapaper, Pocket — different problem)
- Not a spaced repetition system (Anki is better at that)
- Not a writing tool (notes are for capture, not for publishing)

---

**Status:** Ready for M1 scaffold.  
**Next step:** GitHub repo, Docker Compose, FastAPI scaffold, SvelteKit shell.
