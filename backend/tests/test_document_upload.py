from __future__ import annotations

import asyncio
import hashlib
import importlib
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from uuid import uuid4

from fastapi import UploadFile
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.models import Document, Job
from app.uploads import create_document_upload


class DocumentUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise unittest.SkipTest("DATABASE_URL is required for document upload tests")

        cls._original_env = {
            "DATABASE_URL": os.environ.get("DATABASE_URL"),
            "DATA_DIR": os.environ.get("DATA_DIR"),
        }
        cls._tempdir = tempfile.TemporaryDirectory()
        cls.data_dir = Path(cls._tempdir.name)

        base_url = make_url(database_url)
        cls.database_name = f"maktaba_upload_{uuid4().hex}"
        cls.admin_database_url = cls._render_url(base_url.set(database="postgres"))
        cls.test_database_url = cls._render_url(base_url.set(database=cls.database_name))
        cls._create_test_database()

        os.environ["DATABASE_URL"] = cls.test_database_url
        os.environ["DATA_DIR"] = str(cls.data_dir)

        import app.db as db_module
        import app.main as main_module

        cls.db_module = importlib.reload(db_module)
        cls.main_module = importlib.reload(main_module)
        cls.db_module.bootstrap_database()
        cls.client = TestClient(cls.main_module.app)

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            if hasattr(cls, "client"):
                cls.client.close()
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
    def _build_pdf_bytes(title: str, author: str, creation_date: str) -> bytes:
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.add_metadata(
            {
                "/Title": title,
                "/Author": author,
                "/CreationDate": creation_date,
            },
        )
        buffer = io.BytesIO()
        writer.write(buffer)
        return buffer.getvalue()

    @staticmethod
    def _build_epub_bytes(title: str, author: str, publication_date: str) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "mimetype",
                "application/epub+zip",
                compress_type=zipfile.ZIP_STORED,
            )
            archive.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
            )
            archive.writestr(
                "OEBPS/content.opf",
                f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" xmlns:dc="http://purl.org/dc/elements/1.1/" version="3.0" unique-identifier="bookid">
  <metadata>
    <dc:identifier id="bookid">urn:uuid:{uuid4()}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:date>{publication_date}</dc:date>
  </metadata>
  <manifest>
    <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine>
    <itemref idref="chapter1"/>
  </spine>
</package>
""",
            )
            archive.writestr(
                "OEBPS/chapter1.xhtml",
                """<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
  <head><title>Chapter 1</title></head>
  <body><p>Sample chapter.</p></body>
</html>
""",
            )
        return buffer.getvalue()

    def test_upload_pdf_creates_document_and_jobs(self) -> None:
        pdf_bytes = self._build_pdf_bytes(
            title="Sample PDF Title",
            author="Ada Lovelace",
            creation_date="D:20240424010203Z",
        )
        expected_hash = hashlib.sha256(pdf_bytes).hexdigest()

        response = self.client.post(
            "/api/documents",
            files={"file": ("sample.pdf", pdf_bytes, "application/pdf")},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["created"])
        document = payload["document"]
        self.assertEqual(document["format"], "pdf")
        self.assertEqual(document["title"], "Sample PDF Title")
        self.assertEqual(document["authors"], ["Ada Lovelace"])
        self.assertEqual(document["page_count"], 1)
        self.assertEqual(document["publication_date"], "2024-04-24")
        self.assertEqual(document["file_hash"], expected_hash)
        self.assertTrue(document["file_path"].endswith(f"{expected_hash}.pdf"))
        self.assertTrue(Path(document["file_path"]).is_file())
        self.assertEqual(
            hashlib.sha256(Path(document["file_path"]).read_bytes()).hexdigest(),
            expected_hash,
        )

        job_types = {job["job_type"] for job in payload["jobs"]}
        self.assertEqual(job_types, {"extract_text", "generate_embedding"})
        self.assertEqual({job["status"] for job in payload["jobs"]}, {"pending"})

        with self.db_module.Session(self.db_module.engine) as session:
            stored_documents = session.exec(select(Document)).all()
            stored_jobs = session.exec(select(Job)).all()

        self.assertEqual(len(stored_documents), 1)
        self.assertEqual(len(stored_jobs), 2)

    def test_upload_epub_creates_document_and_jobs(self) -> None:
        epub_bytes = self._build_epub_bytes(
            title="Sample EPUB Title",
            author="Octavia Butler",
            publication_date="2024-04-24",
        )
        expected_hash = hashlib.sha256(epub_bytes).hexdigest()

        response = self.client.post(
            "/api/documents",
            files={"file": ("sample.epub", epub_bytes, "application/epub+zip")},
        )

        self.assertEqual(response.status_code, 201)
        payload = response.json()
        self.assertTrue(payload["created"])
        document = payload["document"]
        self.assertEqual(document["format"], "epub")
        self.assertEqual(document["title"], "Sample EPUB Title")
        self.assertEqual(document["authors"], ["Octavia Butler"])
        self.assertEqual(document["page_count"], 1)
        self.assertEqual(document["publication_date"], "2024-04-24")
        self.assertEqual(document["file_hash"], expected_hash)
        self.assertTrue(document["file_path"].endswith(f"{expected_hash}.epub"))
        self.assertTrue(Path(document["file_path"]).is_file())
        self.assertEqual(
            hashlib.sha256(Path(document["file_path"]).read_bytes()).hexdigest(),
            expected_hash,
        )

        job_types = {job["job_type"] for job in payload["jobs"]}
        self.assertEqual(job_types, {"extract_text", "generate_embedding"})
        self.assertEqual({job["status"] for job in payload["jobs"]}, {"pending"})

        with self.db_module.Session(self.db_module.engine) as session:
            stored_documents = session.exec(select(Document)).all()
            stored_jobs = session.exec(select(Job)).all()

        self.assertEqual(len(stored_documents), 1)
        self.assertEqual(len(stored_jobs), 2)

    def test_duplicate_upload_integrity_error_keeps_existing_file(self) -> None:
        pdf_bytes = self._build_pdf_bytes(
            title="Duplicate PDF Title",
            author="Grace Hopper",
            creation_date="D:20240424010203Z",
        )
        expected_hash = hashlib.sha256(pdf_bytes).hexdigest()
        storage_dir = self.data_dir / "pdfs"
        storage_dir.mkdir(parents=True, exist_ok=True)
        canonical_path = storage_dir / f"{expected_hash}.pdf"
        canonical_path.write_bytes(pdf_bytes)

        upload = UploadFile(filename="duplicate.pdf", file=io.BytesIO(pdf_bytes))

        with self.db_module.Session(self.db_module.engine) as session:
            with mock.patch.object(
                session,
                "flush",
                side_effect=IntegrityError("INSERT", {}, RuntimeError("duplicate key")),
            ):
                with self.assertRaises(IntegrityError):
                    asyncio.run(create_document_upload(session, upload, self.data_dir))

        self.assertTrue(canonical_path.exists())
        self.assertEqual(canonical_path.read_bytes(), pdf_bytes)

    def test_rejects_malformed_pdf_upload(self) -> None:
        malformed_pdf = b"%PDF-1.4\nthis is not a real pdf"

        response = self.client.post(
            "/api/documents",
            files={"file": ("broken.pdf", malformed_pdf, "application/pdf")},
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn("PDF", response.json()["detail"])

    def test_rejects_malformed_epub_upload(self) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "mimetype",
                "application/epub+zip",
                compress_type=zipfile.ZIP_STORED,
            )
            archive.writestr(
                "META-INF/container.xml",
                """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/missing.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
""",
            )

        response = self.client.post(
            "/api/documents",
            files={"file": ("broken.epub", buffer.getvalue(), "application/epub+zip")},
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn("EPUB", response.json()["detail"])

    def test_rejects_unsupported_file_types(self) -> None:
        response = self.client.post(
            "/api/documents",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )

        self.assertEqual(response.status_code, 415)
        self.assertIn("PDF and EPUB", response.json()["detail"])
