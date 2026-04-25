from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import os
from typing import AsyncIterator
from uuid import UUID
from collections import defaultdict

from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from sqlalchemy import select
from pydantic import BaseModel
from pathlib import Path

from app.db import get_session, initialize_database
from app.uploads import create_document_upload
from app.models import Document, Job, Highlight

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

    def _sanitize_document(doc_obj: object) -> dict[str, object]:
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

    for doc in docs:
        result.append({
            "document": _sanitize_document(doc),
            "jobs": [_sanitize_job(job) for job in jobs_by_doc.get(doc.id, [])],
        })
    return {"documents": result}


class HighlightCreate(BaseModel):
    page_number: int
    x: float
    y: float
    width: float
    height: float
    color: str | None = None


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
        extracted_text = page.get_text("text", clip=clip) or ""
        doc.close()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    highlight = Highlight(
        document_id=document_id,
        format="pdf",
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


@app.delete("/api/highlights/{highlight_id}")
def delete_highlight(highlight_id: UUID, session: Session = Depends(get_session)) -> dict[str, object]:
    h = session.get(Highlight, highlight_id)
    if h is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")
    session.delete(h)
    session.commit()
    return {"deleted": True}
