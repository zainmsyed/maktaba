from __future__ import annotations

import importlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

import fitz
from PIL import Image, ImageDraw
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import select

from app.models import Document, Job, Page


class ExtractWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise unittest.SkipTest("DATABASE_URL is required for extract worker tests")

        cls._original_env = {
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
            "DATA_DIR": os.environ.get("DATA_DIR"),
        }
        cls._tempdir = tempfile.TemporaryDirectory()
        cls.data_dir = Path(cls._tempdir.name)

        base_url = make_url(database_url)
        cls.database_name = f"maktaba_extract_{uuid4().hex}"
        cls.admin_database_url = cls._render_url(base_url.set(database="postgres"))
        cls.test_database_url = cls._render_url(base_url.set(database=cls.database_name))
        cls._create_test_database()

        os.environ["DATABASE_URL"] = cls.test_database_url
        os.environ["DATA_DIR"] = str(cls.data_dir)

        import app.db as db_module
        import app.worker as worker_module

        cls.db_module = importlib.reload(db_module)
        cls.worker_module = importlib.reload(worker_module)
        cls.db_module.bootstrap_database()

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if hasattr(cls, "db_module"):
                cls.db_module.engine.dispose()
        finally:
            cls._drop_test_database()
            for key, value in cls._original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            cls._tempdir.cleanup()

    @staticmethod
    def _render_url(url) -> str:
        return url.render_as_string(hide_password=False)

    @classmethod
    def _create_test_database(cls) -> None:
        admin_engine = create_engine(
            cls.admin_database_url,
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        try:
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(
                    f'DROP DATABASE IF EXISTS "{cls.database_name}"',
                )
                connection.exec_driver_sql(
                    f'CREATE DATABASE "{cls.database_name}"',
                )
        finally:
            admin_engine.dispose()

    @classmethod
    def _drop_test_database(cls) -> None:
        admin_engine = create_engine(
            cls.admin_database_url,
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
        try:
            with admin_engine.connect() as connection:
                connection.exec_driver_sql(
                    f'DROP DATABASE IF EXISTS "{cls.database_name}"',
                )
        finally:
            admin_engine.dispose()

    def setUp(self) -> None:
        self._reset_test_database()

    def _reset_test_database(self) -> None:
        with self.db_module.Session(self.db_module.engine) as session:
            session.execute(
                text(
                    "TRUNCATE TABLE documents, pages, highlights, notes, embeddings, jobs, config, entities, triples RESTART IDENTITY CASCADE",
                ),
            )
            session.commit()

    @staticmethod
    def _build_text_pdf(path: Path, pages: list[str]) -> None:
        pdf = fitz.open()
        for page_text in pages:
            page = pdf.new_page(width=595, height=842)
            page.insert_text((72, 72), page_text, fontsize=18)
        pdf.save(str(path))
        pdf.close()

    @staticmethod
    def _build_image_pdf(path: Path, label: str) -> None:
        image = Image.new("RGB", (1200, 1600), "white")
        draw = ImageDraw.Draw(image)
        draw.text((100, 120), label, fill="black")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        pdf = fitz.open()
        page = pdf.new_page(width=image.width, height=image.height)
        page.insert_image(page.rect, stream=buffer.getvalue())
        pdf.save(str(path))
        pdf.close()

    def _create_document_and_job(self, session, file_path: Path, title: str) -> tuple[Document, Job]:
        with fitz.open(str(file_path)) as pdf:
            page_count = pdf.page_count

        document = Document(
            file_path=str(file_path),
            file_hash=uuid4().hex,
            format="pdf",
            title=title,
            authors=["Test Author"],
            page_count=page_count,
        )
        job = Job(
            document_id=document.id,
            job_type="extract_text",
            payload={
                "step": "extract_text",
                "document_id": str(document.id),
                "file_hash": document.file_hash,
                "format": document.format,
                "title": document.title,
                "authors": document.authors,
                "page_count": document.page_count,
            },
        )

        session.add(document)
        session.add(job)
        session.commit()
        session.refresh(document)
        session.refresh(job)
        return document, job

    def test_process_extract_job_persists_text_pdf_pages(self) -> None:
        pdf_path = self.data_dir / "text.pdf"
        self._build_text_pdf(
            pdf_path,
            [
                "This is a sufficiently long text layer for page one to avoid OCR fallback.",
                "This is a sufficiently long text layer for page two to avoid OCR fallback.",
            ],
        )

        with self.db_module.Session(self.db_module.engine) as session:
            document, job = self._create_document_and_job(session, pdf_path, "Text PDF")

            self.worker_module.process_extract_job(session, job)

            pages = session.exec(
                select(Page)
                .where(Page.document_id == document.id)
                .order_by(Page.page_number),
            ).all()
            refreshed_job = session.get(Job, job.id)

        self.assertEqual([page.page_number for page in pages], [1, 2])
        self.assertTrue(pages[0].extracted_text.startswith("This is a sufficiently long text layer for page one"))
        self.assertTrue(pages[1].extracted_text.startswith("This is a sufficiently long text layer for page two"))
        self.assertEqual([page.ocr_used for page in pages], [False, False])
        self.assertIsNotNone(refreshed_job)
        self.assertEqual(refreshed_job.status, "completed")
        self.assertIsNotNone(refreshed_job.completed_at)

    def test_process_extract_job_uses_ocr_for_image_only_pdf(self) -> None:
        pdf_path = self.data_dir / "scanned.pdf"
        self._build_image_pdf(pdf_path, "Scanned page")

        with self.db_module.Session(self.db_module.engine) as session:
            document, job = self._create_document_and_job(session, pdf_path, "Scanned PDF")

            with mock.patch("pytesseract.image_to_string", return_value="OCR extracted text") as ocr_mock:
                self.worker_module.process_extract_job(session, job)

            pages = session.exec(
                select(Page)
                .where(Page.document_id == document.id)
                .order_by(Page.page_number),
            ).all()
            refreshed_job = session.get(Job, job.id)

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].page_number, 1)
        self.assertEqual(pages[0].extracted_text, "OCR extracted text")
        self.assertTrue(pages[0].ocr_used)
        self.assertIsNotNone(refreshed_job)
        self.assertEqual(refreshed_job.status, "completed")
        self.assertIsNotNone(refreshed_job.completed_at)
        self.assertGreaterEqual(len(ocr_mock.mock_calls), 1)

    def test_process_extract_job_rolls_back_pages_on_failure(self) -> None:
        pdf_path = self.data_dir / "failure.pdf"
        self._build_text_pdf(pdf_path, ["Page 1", "Page 2"])

        with self.db_module.Session(self.db_module.engine) as session:
            document, job = self._create_document_and_job(session, pdf_path, "Broken PDF")
            document_id = document.id
            job_id = job.id
            original_add = session.add
            page_add_count = 0

            def add_side_effect(obj):
                nonlocal page_add_count
                if isinstance(obj, Page):
                    page_add_count += 1
                    if page_add_count == 2:
                        raise RuntimeError("boom")
                return original_add(obj)

            with mock.patch.object(session, "add", side_effect=add_side_effect):
                self.worker_module.process_extract_job(session, job)

        with self.db_module.Session(self.db_module.engine) as verify_session:
            pages = verify_session.exec(
                select(Page).where(Page.document_id == document_id),
            ).all()
            refreshed_job = verify_session.get(Job, job_id)

        self.assertEqual(pages, [])
        self.assertIsNotNone(refreshed_job)
        self.assertEqual(refreshed_job.status, "failed")
        self.assertIn("boom", refreshed_job.error_message or "")
        self.assertIsNotNone(refreshed_job.completed_at)
