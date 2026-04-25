from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.db import engine
from app.models import Job, Document, Page
from app.extract import extract_text_and_fallback


logger = logging.getLogger("maktaba.worker")
logging.basicConfig(level=logging.INFO)

SLEEP_SECONDS = 2.0


def _claim_job(session: Session) -> Optional[Job]:
    stmt = select(Job).where(Job.status == "pending", Job.job_type == "extract_text").order_by(Job.created_at)
    job = session.exec(stmt).scalars().first()
    if job is None:
        return None
    job.status = "processing"
    session.add(job)
    session.commit()
    session.refresh(job)
    return job


def process_extract_job(session: Session, job: Job) -> None:
    try:
        if not job.document_id:
            raise RuntimeError("extract_text job has no document_id")

        doc = session.get(Document, job.document_id)
        if doc is None:
            raise RuntimeError("document not found for job")

        pdf_path = doc.file_path
        logger.info("Processing extract_text job %s for document %s", job.id, doc.id)

        # Iterate pages and persist Page rows
        pages_to_add = []
        for page_number, text, ocr_used in extract_text_and_fallback(pdf_path):
            p = Page(
                document_id=doc.id,
                page_number=page_number,
                extracted_text=text or None,
                ocr_used=bool(ocr_used),
            )
            pages_to_add.append(p)

        # Bulk insert pages; if rows already exist (e.g., reprocessing), replace them
        for p in pages_to_add:
            # try to find existing page
            existing = session.exec(
                select(Page).where(Page.document_id == p.document_id, Page.page_number == p.page_number)
            ).scalars().first()
            if existing is None:
                session.add(p)
            else:
                existing.extracted_text = p.extracted_text
                existing.ocr_used = p.ocr_used
                session.add(existing)

        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        session.add(job)
        session.commit()
        logger.info("Completed extract_text job %s", job.id)
    except Exception as exc:
        logger.exception("Failed to process extract_text job %s: %s", getattr(job, "id", None), exc)
        job.status = "failed"
        job.error_message = str(exc)
        session.add(job)
        session.commit()


def run_once() -> None:
    """Process a single pending extract_text job if present."""
    with Session(engine) as session:
        job = _claim_job(session)
        if not job:
            return
        process_extract_job(session, job)


def run_loop(poll_interval: float = SLEEP_SECONDS) -> None:
    logger.info("Starting worker loop (extract_text)")
    try:
        while True:
            try:
                run_once()
            except Exception:
                logger.exception("Worker loop iteration failed")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("Worker loop interrupted by user")


if __name__ == "__main__":
    run_loop()
