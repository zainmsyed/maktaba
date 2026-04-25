from __future__ import annotations

import hashlib
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from fastapi import HTTPException, UploadFile, status
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from app.models import Document, Job

CHUNK_SIZE = 1024 * 1024
SUPPORTED_FORMATS: dict[str, str] = {
    ".pdf": "pdf",
    ".epub": "epub",
}
PDF_MAGIC = b"%PDF-"
EPUB_MIMETYPE = b"application/epub+zip"
EPUB_CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"
EPUB_OPF_NS = "http://www.idpf.org/2007/opf"
EPUB_DC_NS = "http://purl.org/dc/elements/1.1/"
PDF_DATE_RE = re.compile(r"^D:(\d{4})(\d{2})(\d{2})")


@dataclass(slots=True)
class ExtractedDocumentMetadata:
    title: str
    authors: list[str]
    publication_date: date | None
    page_count: int | None


@dataclass(slots=True)
class DocumentUploadResult:
    created: bool
    document: Document
    jobs: list[Job]


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip()
    return cleaned or None


def _split_people(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[;,]", value) if part.strip()]


def _fallback_title(filename: str | None) -> str:
    if not filename:
        return "untitled"
    stem = Path(filename).stem.strip()
    return _clean_text(stem) or _clean_text(filename) or "untitled"


def _parse_pdf_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    text = _clean_text(value)
    if not text:
        return None
    match = PDF_DATE_RE.match(text)
    if match:
        year, month, day = match.groups()
        try:
            return date(int(year), int(month), int(day))
        except ValueError:
            return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


async def _persist_upload(upload: UploadFile, destination_dir: Path) -> tuple[Path, str]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    with tempfile.NamedTemporaryFile(
        delete=False,
        dir=destination_dir,
        prefix=".upload-",
        suffix=Path(upload.filename or "upload").suffix.lower(),
    ) as handle:
        try:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                digest.update(chunk)
                handle.write(chunk)
            os.fchmod(handle.fileno(), 0o644)
        except Exception:
            temp_path = Path(handle.name)
            handle.close()
            temp_path.unlink(missing_ok=True)
            raise
    return Path(handle.name), digest.hexdigest()


def _validate_pdf(path: Path) -> None:
    with path.open("rb") as handle:
        if handle.read(len(PDF_MAGIC)) != PDF_MAGIC:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Uploaded file is not a valid PDF.",
            )


def _validate_epub(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file is not a valid EPUB archive.",
        )

    with zipfile.ZipFile(path) as archive:
        try:
            mimetype = archive.read("mimetype")
        except KeyError as exc:  # pragma: no cover - defensive
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="Uploaded EPUB is missing its mimetype declaration.",
            ) from exc

    if mimetype.strip() != EPUB_MIMETYPE:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file is not a valid EPUB archive.",
        )


def _extract_pdf_metadata(path: Path, fallback_title: str) -> ExtractedDocumentMetadata:
    title = fallback_title
    authors: list[str] = []
    publication_date: date | None = None
    page_count: int | None = None

    try:
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        metadata = reader.metadata
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file is not a valid PDF.",
        ) from exc

    if metadata is not None:
        title = _clean_text(getattr(metadata, "title", None) or metadata.get("/Title")) or title
        authors = _split_people(
            _clean_text(
                getattr(metadata, "author", None)
                or metadata.get("/Author")
                or getattr(metadata, "creator", None)
                or metadata.get("/Creator"),
            ),
        )
        publication_date = _parse_pdf_date(
            getattr(metadata, "creation_date", None)
            or metadata.get("/CreationDate")
            or metadata.get("/ModDate"),
        )

    return ExtractedDocumentMetadata(
        title=title,
        authors=authors,
        publication_date=publication_date,
        page_count=page_count,
    )


def _extract_epub_metadata(path: Path, fallback_title: str) -> ExtractedDocumentMetadata:
    title = fallback_title
    authors: list[str] = []
    publication_date: date | None = None
    page_count: int | None = None

    try:
        with zipfile.ZipFile(path) as archive:
            mimetype = archive.read("mimetype")
            if mimetype.strip() != EPUB_MIMETYPE:
                raise ValueError("Invalid EPUB mimetype")

            container_xml = archive.read("META-INF/container.xml")
            container_root = ET.fromstring(container_xml)
            rootfile = container_root.find(
                f".//{{{EPUB_CONTAINER_NS}}}rootfile",
            )
            if rootfile is None:
                raise ValueError("Missing EPUB rootfile reference")

            opf_path = rootfile.attrib["full-path"]
            opf_root = ET.fromstring(archive.read(opf_path))
            metadata_element = opf_root.find(f"{{{EPUB_OPF_NS}}}metadata")
            spine_element = opf_root.find(f"{{{EPUB_OPF_NS}}}spine")

            if metadata_element is not None:
                title = (
                    _clean_text(metadata_element.findtext(f"{{{EPUB_DC_NS}}}title"))
                    or title
                )
                authors = [
                    person
                    for person in (
                        _clean_text(element.text)
                        for element in metadata_element.findall(f"{{{EPUB_DC_NS}}}creator")
                    )
                    if person
                ]
                raw_date = _clean_text(metadata_element.findtext(f"{{{EPUB_DC_NS}}}date"))
                if raw_date:
                    try:
                        publication_date = date.fromisoformat(raw_date[:10])
                    except ValueError:
                        publication_date = None

            if spine_element is not None:
                page_count = len(spine_element.findall(f"{{{EPUB_OPF_NS}}}itemref")) or None
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Uploaded file is not a valid EPUB archive.",
        ) from exc

    return ExtractedDocumentMetadata(
        title=title,
        authors=authors,
        publication_date=publication_date,
        page_count=page_count,
    )


def _extract_document_metadata(
    path: Path,
    document_format: str,
    fallback_title: str,
) -> ExtractedDocumentMetadata:
    if document_format == "pdf":
        return _extract_pdf_metadata(path, fallback_title)
    if document_format == "epub":
        return _extract_epub_metadata(path, fallback_title)
    raise ValueError(f"Unsupported document format: {document_format}")


def _job_payload(document: Document, step: str) -> dict[str, Any]:
    return {
        "step": step,
        "document_id": str(document.id),
        "file_path": document.file_path,
        "file_hash": document.file_hash,
        "format": document.format,
        "title": document.title,
        "authors": document.authors,
        "page_count": document.page_count,
    }


async def create_document_upload(
    session: Session,
    upload: UploadFile,
    data_dir: Path,
) -> DocumentUploadResult:
    filename = upload.filename or "upload"
    suffix = Path(filename).suffix.lower()
    document_format = SUPPORTED_FORMATS.get(suffix)
    if document_format is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF and EPUB files are supported.",
        )

    storage_dir = data_dir / f"{document_format}s"
    temp_path: Path | None = None
    final_path: Path | None = None
    file_hash = ""
    moved_to_final = False

    try:
        temp_path, file_hash = await _persist_upload(upload, storage_dir)
        if document_format == "pdf":
            _validate_pdf(temp_path)
        else:
            _validate_epub(temp_path)

        metadata = _extract_document_metadata(
            temp_path,
            document_format,
            _fallback_title(filename),
        )
        final_path = storage_dir / f"{file_hash}{suffix}"

        existing = session.exec(
            select(Document).where(
                Document.file_hash == file_hash,
                Document.format == document_format,
            ),
        ).scalars().first()
        if existing is not None:
            # resolve existing id in a robust way (Document instance or Row mapping)
            existing_id = None
            if hasattr(existing, "id"):
                existing_id = existing.id
            else:
                try:
                    existing_id = existing["id"]
                except Exception:
                    try:
                        existing_id = existing._mapping["id"]
                    except Exception:
                        # as a last resort, re-query the id directly
                        existing_id = session.exec(
                            select(Document.id).where(
                                Document.file_hash == file_hash,
                                Document.format == document_format,
                            )
                        ).scalar_one_or_none()

            # fetch jobs while we have the id
            existing_jobs = []
            if existing_id is not None:
                existing_jobs = session.exec(
                    select(Job)
                    .where(Job.document_id == existing_id)
                    .order_by(Job.created_at, Job.id),
                ).scalars().all()

            # no DB changes were performed; clean up the temp file and return existing document
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
            return DocumentUploadResult(
                created=False,
                document=existing,
                jobs=existing_jobs,
            )

        document = Document(
            file_path=str(final_path),
            file_hash=file_hash,
            format=document_format,
            title=metadata.title,
            authors=metadata.authors,
            publication_date=metadata.publication_date,
            page_count=metadata.page_count,
        )
        extract_job = Job(
            document_id=document.id,
            job_type="extract_text",
            payload=_job_payload(document, "extract_text"),
        )
        embedding_job = Job(
            document_id=document.id,
            job_type="generate_embedding",
            payload=_job_payload(document, "generate_embedding"),
        )

        session.add(document)
        session.add_all([extract_job, embedding_job])
        session.flush()
        os.replace(temp_path, final_path)
        moved_to_final = True
        session.commit()
        session.refresh(document)
        session.refresh(extract_job)
        session.refresh(embedding_job)
        return DocumentUploadResult(
            created=True,
            document=document,
            jobs=[extract_job, embedding_job],
        )
    except IntegrityError:
        session.rollback()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if moved_to_final and final_path is not None:
            final_path.unlink(missing_ok=True)

        existing = session.exec(
            select(Document).where(
                Document.file_hash == file_hash,
                Document.format == document_format,
            ),
        ).scalars().first()
        if existing is not None:
            existing_jobs = session.exec(
                select(Job)
                .where(Job.document_id == existing.id)
                .order_by(Job.created_at, Job.id),
            ).scalars().all()
            return DocumentUploadResult(
                created=False,
                document=existing,
                jobs=existing_jobs,
            )
        raise
    except HTTPException:
        session.rollback()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if moved_to_final and final_path is not None:
            final_path.unlink(missing_ok=True)
        raise
    except Exception:
        session.rollback()
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        if moved_to_final and final_path is not None:
            final_path.unlink(missing_ok=True)
        raise
