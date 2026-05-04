from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import logging
import os
from typing import AsyncIterator, Literal
from datetime import datetime, timezone
from uuid import UUID
from collections import defaultdict

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from sqlalchemy import delete as sa_delete, func, select, text, literal, cast, String
from pydantic import BaseModel

from app.db import get_session, initialize_database
from app.uploads import create_document_upload
from app.models import Document, Folder, Job, Page, Highlight, Note, Embedding

logger = logging.getLogger("maktaba.api")

DATA_DIR = Path(os.getenv("DATA_DIR", "/data")).resolve()
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    ).split(",")
    if origin.strip()
]


def ensure_data_directories() -> None:
    for name in ("pdfs", "epubs", "thumbs"):
        (DATA_DIR / name).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    ensure_data_directories()
    initialize_database()
    yield


app = FastAPI(title="Maktaba API", lifespan=lifespan)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Shared response sanitizers used by endpoints to avoid leaking internal file paths
# in the public JSON payloads. Defined at module scope to avoid duplication.
def _sanitize_document(doc_obj: object) -> dict[str, object]:
    # Accept either a SQLModel instance or a mapping returned by lower-level
    # code; produce a shallow JSON-serializable dict with internal paths
    # removed.
    try:
        doc = doc_obj.model_dump(mode="json")
    except Exception:
        doc = dict(doc_obj)
    doc.pop("file_path", None)
    doc.pop("cover_path", None)
    return doc


def _serialize_folder(folder: Folder) -> dict[str, object]:
    return {
        "id": str(folder.id),
        "name": folder.name,
        "created_at": folder.created_at.isoformat() if folder.created_at else None,
        "updated_at": folder.updated_at.isoformat() if folder.updated_at else None,
    }


def _sanitize_job(job_obj: object) -> dict[str, object]:
    try:
        j = job_obj.model_dump(mode="json")
    except Exception:
        j = dict(job_obj)
    payload = j.get("payload")
    if isinstance(payload, dict):
        payload = payload.copy()
        payload.pop("file_path", None)
        j["payload"] = payload
    return j


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Maktaba backend is running",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "backend",
        "data_dir": str(DATA_DIR),
        "storage_dirs": {
            "pdfs": str(DATA_DIR / "pdfs"),
            "epubs": str(DATA_DIR / "epubs"),
            "thumbs": str(DATA_DIR / "thumbs"),
        },
    }


@app.get("/api/documents/{document_id}/file")
def stream_document_file(
    document_id: UUID,
    session: Session = Depends(get_session),
) -> StreamingResponse:
    document = session.exec(
        select(Document).where(Document.id == document_id),
    ).scalars().first()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if document.format != "pdf":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF documents can be streamed from this endpoint.",
        )

    # Try the stored path first (usually absolute inside the container),
    # then fall back to resolving under DATA_DIR for local dev setups
    # where the backend runs outside Docker.
    stored_path = Path(document.file_path)
    candidates = [stored_path]
    if stored_path.is_absolute():
        # e.g. /data/pdfs/abc.pdf → resolve under DATA_DIR/pdfs/abc.pdf
        relative = stored_path.relative_to(stored_path.anchor) if stored_path.anchor else stored_path
        candidates.append(DATA_DIR / relative)
    else:
        candidates.append(DATA_DIR / stored_path)

    file_path: Path | None = None
    for candidate in candidates:
        logger.info("Checking file path candidate: %s (exists=%s)", candidate, candidate.is_file())
        if candidate.is_file():
            file_path = candidate
            break

    if file_path is None:
        logger.error(
            "Document %s file not found. Stored path: %s. DATA_DIR: %s. Checked: %s",
            document_id,
            document.file_path,
            DATA_DIR,
            [str(c) for c in candidates],
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found.",
        )

    def iter_pdf_bytes():
        with file_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iter_pdf_bytes(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{file_path.name}"'},
    )


@app.post("/api/documents")
async def upload_document(
    response: Response,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    result = await create_document_upload(session, file, DATA_DIR)
    response.status_code = (
        status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
    )

    return {
        "created": result.created,
        "document": _sanitize_document(result.document),
        "jobs": [_sanitize_job(job) for job in result.jobs],
    }


@app.get("/api/documents")
def list_documents(
    folder_id: str | None = None,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    """Return non-deleted documents with their associated jobs.

    The structure mirrors the POST /api/documents response. Jobs are fetched
    in a single batched query to avoid N+1 query patterns. Optionally filter
    by folder_id; pass folder_id=null for uncategorized documents.
    """
    stmt = select(Document).where(Document.deleted_at.is_(None))
    if folder_id is not None:
        if folder_id.lower() in ("null", "none", ""):
            stmt = stmt.where(Document.folder_id.is_(None))
        else:
            try:
                fid = UUID(folder_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid folder_id")
            stmt = stmt.where(Document.folder_id == fid)
    stmt = stmt.order_by(Document.updated_at.desc())
    docs = session.exec(stmt).scalars().all()

    result: list[dict[str, object]] = []

    doc_ids = [d.id for d in docs]
    jobs_by_doc: dict[object, list[Job]] = defaultdict(list)
    if doc_ids:
        jobs = session.exec(
            select(Job).where(Job.document_id.in_(doc_ids)).order_by(Job.created_at, Job.id)
        ).scalars().all()
        for j in jobs:
            jobs_by_doc[j.document_id].append(j)

    hl_counts: dict[object, int] = {}
    note_counts: dict[object, int] = {}
    if doc_ids:
        hl_rows = session.exec(
            select(Highlight.document_id, func.count(Highlight.id))
            .where(Highlight.document_id.in_(doc_ids))
            .group_by(Highlight.document_id)
        ).all()
        hl_counts = {row[0]: row[1] for row in hl_rows}

        note_rows = session.exec(
            select(Note.document_id, func.count(Note.id))
            .where(Note.document_id.in_(doc_ids))
            .group_by(Note.document_id)
        ).all()
        note_counts = {row[0]: row[1] for row in note_rows}

    for doc in docs:
        result.append({
            "document": _sanitize_document(doc),
            "jobs": [_sanitize_job(job) for job in jobs_by_doc.get(doc.id, [])],
            "highlight_count": hl_counts.get(doc.id, 0),
            "note_count": note_counts.get(doc.id, 0),
        })
    return {"documents": result}


HighlightColor = Literal["yellow", "green", "blue", "red"]


class HighlightCreate(BaseModel):
    page_number: int
    x: float
    y: float
    width: float
    height: float
    color: HighlightColor | None = None
    extracted_text: str | None = None
    highlight_type: str | None = None
    rects: list[dict[str, object]] | None = None


class HighlightUpdate(BaseModel):
    color: HighlightColor


class NoteCreate(BaseModel):
    content: str = ""
    highlight_id: UUID | None = None


class NoteUpdate(BaseModel):
    content: str


class FolderCreate(BaseModel):
    name: str


class FolderUpdate(BaseModel):
    name: str


class DocumentUpdate(BaseModel):
    folder_id: UUID | None = None


class SearchResult(BaseModel):
    id: str
    source_type: str
    document_id: str
    document_title: str | None
    page_number: int | None
    content: str
    highlight_id: str | None
    rank: float


def serialize_highlight(highlight: Highlight) -> dict[str, object]:
    payload = highlight.model_dump(mode="json")
    payload.pop("fts", None)
    return payload


def serialize_note(note: Note, highlight: Highlight | None = None) -> dict[str, object]:
    payload = note.model_dump(mode="json")
    payload.pop("fts", None)
    payload["page_number"] = highlight.page_number if highlight is not None else None
    payload["highlight"] = serialize_highlight(highlight) if highlight is not None else None
    return payload


@app.post("/api/documents/{document_id}/highlights")
def create_highlight(
    document_id: UUID,
    payload: HighlightCreate = Body(...),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    document = session.exec(select(Document).where(Document.id == document_id)).scalars().first()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if (document.format or "").lower() != "pdf":
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only PDF highlights are supported.")

    # derive extracted text from the PDF using PyMuPDF for the provided normalized geometry
    try:
        import fitz
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="PDF extraction not available")

    pdf_path = Path(document.file_path)
    if not pdf_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file not found")

    try:
        doc = fitz.open(str(pdf_path))
        page = doc.load_page(payload.page_number - 1)
        pw = page.rect.width
        ph = page.rect.height
        clip = fitz.Rect(
            payload.x * pw,
            payload.y * ph,
            (payload.x + payload.width) * pw,
            (payload.y + payload.height) * ph,
        )
        extracted_text = (payload.extracted_text or "").strip()
        if not extracted_text:
            extracted_text = page.get_text("text", clip=clip) or ""
        doc.close()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    highlight = Highlight(
        document_id=document_id,
        format="pdf",
        highlight_type=payload.highlight_type if payload.highlight_type in {"text", "area"} else "area",
        rects=payload.rects,
        page_number=payload.page_number,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        extracted_text=extracted_text,
        color=payload.color or "yellow",
    )
    session.add(highlight)
    session.commit()
    session.refresh(highlight)

    h = highlight.model_dump(mode="json")
    # remove fts column if present
    h.pop("fts", None)
    return {"highlight": h}


@app.get("/api/documents/{document_id}/highlights")
def list_highlights(document_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    highlights = session.exec(select(Highlight).where(Highlight.document_id == document_id).order_by(Highlight.created_at)).scalars().all()
    result = []
    for h in highlights:
        try:
            obj = h.model_dump(mode="json")
        except Exception:
            obj = dict(h)
        obj.pop("fts", None)
        result.append(obj)
    return {"highlights": result}


@app.patch("/api/highlights/{highlight_id}")
def update_highlight(
    highlight_id: UUID,
    payload: HighlightUpdate = Body(...),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    highlight = session.get(Highlight, highlight_id)
    if highlight is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")

    highlight.color = payload.color
    session.add(highlight)
    session.commit()
    session.refresh(highlight)

    return {"highlight": serialize_highlight(highlight)}


@app.get("/api/documents/{document_id}/notes")
def list_notes(document_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    notes = session.exec(
        select(Note).where(Note.document_id == document_id).order_by(Note.created_at, Note.id),
    ).scalars().all()
    highlight_ids = [note.highlight_id for note in notes if note.highlight_id is not None]
    highlights_by_id: dict[UUID, Highlight] = {}
    if highlight_ids:
        highlights = session.exec(
            select(Highlight).where(
                Highlight.document_id == document_id,
                Highlight.id.in_(highlight_ids),
            ),
        ).scalars().all()
        highlights_by_id = {highlight.id: highlight for highlight in highlights}

    result = [serialize_note(note, highlights_by_id.get(note.highlight_id)) for note in notes]
    result.sort(
        key=lambda item: (
            item["page_number"] is None,
            item["page_number"] if item["page_number"] is not None else 0,
            item["updated_at"] or item["created_at"] or "",
            item["id"],
        ),
    )
    return {"notes": result}


@app.post("/api/documents/{document_id}/notes")
def create_note(
    response: Response,
    document_id: UUID,
    payload: NoteCreate = Body(...),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    highlight: Highlight | None = None
    if payload.highlight_id is not None:
        highlight = session.exec(
            select(Highlight).where(
                Highlight.id == payload.highlight_id,
                Highlight.document_id == document_id,
            ),
        ).scalars().first()
        if highlight is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found for document")

    note = Note(
        document_id=document_id,
        highlight_id=payload.highlight_id,
        content=payload.content,
    )
    session.add(note)
    session.commit()
    session.refresh(note)
    response.status_code = status.HTTP_201_CREATED
    return {"note": serialize_note(note, highlight)}


@app.patch("/api/notes/{note_id}")
def update_note(
    note_id: UUID,
    payload: NoteUpdate = Body(...),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    note = session.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    note.content = payload.content
    session.add(note)
    session.commit()
    session.refresh(note)

    highlight: Highlight | None = None
    if note.highlight_id is not None:
        highlight = session.get(Highlight, note.highlight_id)
        if highlight is not None and highlight.document_id != note.document_id:
            highlight = None

    return {"note": serialize_note(note, highlight)}


@app.delete("/api/notes/{note_id}")
def delete_note(
    note_id: UUID,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    note = session.get(Note, note_id)
    if note is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    session.delete(note)
    session.commit()
    return {"deleted": True}


@app.get("/api/search")
def search(
    q: str,
    limit: int = 50,
    session: Session = Depends(get_session),
) -> dict[str, object]:
    if not q or not q.strip():
        return {"results": [], "query": q}

    ts_query = func.plainto_tsquery("english", q.strip())

    highlight_stmt = (
        select(
            Highlight.id,
            literal("highlight").label("source_type"),
            Highlight.document_id,
            Document.title.label("document_title"),
            Highlight.page_number,
            Highlight.extracted_text.label("content"),
            cast(None, String).label("highlight_id"),
            func.ts_rank_cd(Highlight.fts, ts_query).label("rank"),
        )
        .join(Document, Highlight.document_id == Document.id)
        .where(
            Highlight.fts.op("@@")(ts_query),
            Document.deleted_at.is_(None),
        )
    )

    note_stmt = (
        select(
            Note.id,
            literal("note").label("source_type"),
            Note.document_id,
            Document.title.label("document_title"),
            Highlight.page_number,
            Note.content,
            cast(Note.highlight_id, String).label("highlight_id"),
            func.ts_rank_cd(Note.fts, ts_query).label("rank"),
        )
        .join(Document, Note.document_id == Document.id)
        .outerjoin(Highlight, Note.highlight_id == Highlight.id)
        .where(
            Note.fts.op("@@")(ts_query),
            Document.deleted_at.is_(None),
        )
    )

    # Document search by title and authors (no persisted fts; compute on the fly)
    doc_ts_query = func.plainto_tsquery("english", q.strip())
    doc_stmt = (
        select(
            Document.id,
            literal("document").label("source_type"),
            Document.id.label("document_id"),
            Document.title.label("document_title"),
            cast(None, Integer).label("page_number"),
            func.coalesce(Document.title, "").label("content"),
            cast(None, String).label("highlight_id"),
            func.ts_rank_cd(
                func.to_tsvector("english", func.coalesce(Document.title, "") + " " + func.array_to_string(Document.authors, " ")),
                doc_ts_query,
            ).label("rank"),
        )
        .where(
            Document.deleted_at.is_(None),
            func.to_tsvector("english", func.coalesce(Document.title, "") + " " + func.array_to_string(Document.authors, " ")).op("@@")(doc_ts_query),
        )
    )

    union_stmt = (
        highlight_stmt.union_all(note_stmt).union_all(doc_stmt)
        .order_by(text("rank DESC"))
        .limit(limit)
    )
    rows = session.exec(union_stmt).all()

    results = []
    seen_doc_ids = set()
    for row in rows:
        doc_id = str(row.document_id)
        # deduplicate document results so a document only appears once
        if row.source_type == "document" and doc_id in seen_doc_ids:
            continue
        if row.source_type == "document":
            seen_doc_ids.add(doc_id)
        results.append({
            "id": str(row.id),
            "source_type": row.source_type,
            "document_id": doc_id,
            "document_title": row.document_title,
            "page_number": row.page_number,
            "content": row.content,
            "highlight_id": str(row.highlight_id) if row.highlight_id else None,
            "rank": float(row.rank) if row.rank is not None else 0.0,
        })

    return {"results": results, "query": q.strip(), "count": len(results)}


@app.delete("/api/highlights/{highlight_id}")
def delete_highlight(highlight_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    h = session.get(Highlight, highlight_id)
    if h is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")

    # Delete dependent notes explicitly so highlight deletion works even if an
    # older database was created before the ON DELETE CASCADE constraint existed.
    session.execute(sa_delete(Note).where(Note.highlight_id == highlight_id))
    session.delete(h)
    session.commit()
    return {"deleted": True}


@app.patch("/api/documents/{document_id}")
def update_document(
    document_id: UUID,
    payload: DocumentUpdate = Body(...),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    doc = session.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if payload.folder_id is not None:
        folder = session.get(Folder, payload.folder_id)
        if folder is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
        doc.folder_id = payload.folder_id
    else:
        doc.folder_id = None

    session.add(doc)
    session.commit()
    session.refresh(doc)
    return {"document": _sanitize_document(doc)}


@app.get("/api/folders")
def list_folders(session: Session = Depends(get_session)) -> dict[str, object]:
    folders = session.exec(select(Folder).order_by(Folder.name)).scalars().all()
    return {"folders": [_serialize_folder(f) for f in folders]}


@app.post("/api/folders")
def create_folder(
    response: Response,
    payload: FolderCreate = Body(...),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Folder name is required")
    folder = Folder(name=name)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    response.status_code = status.HTTP_201_CREATED
    return {"folder": _serialize_folder(folder)}


@app.patch("/api/folders/{folder_id}")
def update_folder(
    folder_id: UUID,
    payload: FolderUpdate = Body(...),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    folder = session.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Folder name is required")
    folder.name = name
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return {"folder": _serialize_folder(folder)}


@app.delete("/api/folders/{folder_id}")
def delete_folder(folder_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    folder = session.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    # unset folder_id on related documents
    from sqlalchemy import update as sa_update
    session.execute(
        sa_update(Document).where(Document.folder_id == folder_id).values(folder_id=None)
    )
    session.delete(folder)
    session.commit()
    return {"deleted": True}


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    """Soft-delete a document and remove related rows and files.

    The document row is marked with deleted_at so it is excluded from
    listings; associated jobs, pages, highlights, notes and embeddings are
    removed immediately to free storage. Physical files (PDF/EPUB/cover)
    are also deleted from the DATA_DIR if present. This operation is
    idempotent.
    """
    doc = session.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    # mark as deleted
    now = datetime.now(timezone.utc)
    doc.deleted_at = now
    session.add(doc)

    # remove jobs related to this document
    session.execute(sa_delete(Job).where(Job.document_id == document_id))

    # collect related source ids for embeddings and explicit deletion
    page_rows = session.exec(select(Page.id).where(Page.document_id == document_id)).all()
    page_ids = [r[0] for r in page_rows] if page_rows else []
    hl_rows = session.exec(select(Highlight.id).where(Highlight.document_id == document_id)).all()
    highlight_ids = [r[0] for r in hl_rows] if hl_rows else []
    note_rows = session.exec(select(Note.id).where(Note.document_id == document_id)).all()
    note_ids = [r[0] for r in note_rows] if note_rows else []

    # delete embeddings for pages/highlights/notes
    if page_ids:
        session.execute(sa_delete(Embedding).where(Embedding.source_type == 'page', Embedding.source_id.in_(page_ids)))
    if highlight_ids:
        session.execute(sa_delete(Embedding).where(Embedding.source_type == 'highlight', Embedding.source_id.in_(highlight_ids)))
    if note_ids:
        session.execute(sa_delete(Embedding).where(Embedding.source_type == 'note', Embedding.source_id.in_(note_ids)))

    # explicitly delete notes, highlights and pages so data isn't retained
    session.execute(sa_delete(Note).where(Note.document_id == document_id))
    session.execute(sa_delete(Highlight).where(Highlight.document_id == document_id))
    session.execute(sa_delete(Page).where(Page.document_id == document_id))

    session.commit()

    # remove files on disk if possible; ignore errors
    try:
        if doc.file_path:
            p = Path(doc.file_path)
            if p.exists():
                p.unlink()
        if getattr(doc, "cover_path", None):
            cp = Path(doc.cover_path)
            if cp.exists():
                cp.unlink()
    except Exception:
        pass

    return {"deleted": True}
