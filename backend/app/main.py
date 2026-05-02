from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import os
from typing import AsyncIterator, Literal
from uuid import UUID
from collections import defaultdict

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from sqlalchemy import delete as sa_delete, func, select, text
from pydantic import BaseModel

from app.db import get_session, initialize_database
from app.uploads import create_document_upload
from app.models import Document, Job, Highlight, Note

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

    file_path = Path(document.file_path)
    if not file_path.is_file():
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
def list_documents(session: Session = Depends(get_session)) -> dict[str, object]:
    """Return all non-deleted documents with their associated jobs.

    The structure mirrors the POST /api/documents response for ease of
    consumption by the frontend. Jobs are fetched in a single batched query
    to avoid N+1 query patterns.
    """
    docs = session.exec(
        select(Document).where(Document.deleted_at.is_(None)).order_by(Document.updated_at.desc())
    ).scalars().all()

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
            text("'highlight'").label("source_type"),
            Highlight.document_id,
            Document.title.label("document_title"),
            Highlight.page_number,
            Highlight.extracted_text.label("content"),
            func.cast(None, func.typeof(Highlight.id)).label("highlight_id"),
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
            text("'note'").label("source_type"),
            Note.document_id,
            Document.title.label("document_title"),
            Highlight.page_number,
            Note.content,
            Note.highlight_id,
            func.ts_rank_cd(Note.fts, ts_query).label("rank"),
        )
        .join(Document, Note.document_id == Document.id)
        .outerjoin(Highlight, Note.highlight_id == Highlight.id)
        .where(
            Note.fts.op("@@")(ts_query),
            Document.deleted_at.is_(None),
        )
    )

    union_stmt = highlight_stmt.union_all(note_stmt).order_by(text("rank DESC")).limit(limit)
    rows = session.exec(union_stmt).all()

    results = []
    for row in rows:
        results.append({
            "id": str(row.id),
            "source_type": row.source_type,
            "document_id": str(row.document_id),
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
