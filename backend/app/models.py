from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Folder(SQLModel, table=True):
    __tablename__ = "folders"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


class Document(SQLModel, table=True):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "format IN ('pdf', 'epub')",
            name="ck_documents_format",
        ),
        Index(
            "idx_documents_deleted",
            "deleted_at",
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("idx_documents_folder", "folder_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    file_path: str = Field(sa_column=Column(Text, nullable=False, unique=True))
    file_hash: str = Field(sa_column=Column(Text, nullable=False))
    format: str = Field(sa_column=Column(String, nullable=False))
    title: str | None = Field(default=None, sa_column=Column(Text))
    authors: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            ARRAY(Text()),
            nullable=False,
            server_default=text("'{}'::text[]"),
        ),
    )
    publication_date: date | None = Field(default=None, sa_column=Column(Date))
    page_count: int | None = Field(default=None, sa_column=Column(Integer))
    cover_path: str | None = Field(default=None, sa_column=Column(Text))
    tags: list[str] = Field(
        default_factory=list,
        sa_column=Column(
            ARRAY(Text()),
            nullable=False,
            server_default=text("'{}'::text[]"),
        ),
    )
    reading_progress: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    folder_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("folders.id", ondelete="SET NULL"), nullable=True),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


class Page(SQLModel, table=True):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "page_number",
            name="uq_pages_document_page",
        ),
        Index("idx_pages_document", "document_id"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(
        sa_column=Column(
            ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    page_number: int = Field(sa_column=Column(Integer, nullable=False))
    extracted_text: str | None = Field(default=None, sa_column=Column(Text))
    ocr_used: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    thumbnail_path: str | None = Field(default=None, sa_column=Column(Text))


class Highlight(SQLModel, table=True):
    __tablename__ = "highlights"
    __table_args__ = (
        CheckConstraint(
            "format IN ('pdf', 'epub', 'kindle')",
            name="ck_highlights_format",
        ),
        CheckConstraint(
            "color IN ('yellow', 'green', 'blue', 'red')",
            name="ck_highlights_color",
        ),
        CheckConstraint(
            "highlight_type IN ('text', 'area')",
            name="ck_highlights_type",
        ),
        Index("idx_highlights_document", "document_id"),
        Index("idx_highlights_fts", "fts", postgresql_using="gin"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(
        sa_column=Column(
            ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    format: str = Field(sa_column=Column(String, nullable=False))
    highlight_type: str = Field(
        default="area",
        sa_column=Column(String, nullable=False, server_default=text("'area'")),
    )
    rects: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSONB))
    page_number: int | None = Field(default=None, sa_column=Column(Integer))
    x: float | None = Field(default=None, sa_column=Column(Float))
    y: float | None = Field(default=None, sa_column=Column(Float))
    width: float | None = Field(default=None, sa_column=Column(Float))
    height: float | None = Field(default=None, sa_column=Column(Float))
    cfi_range: str | None = Field(default=None, sa_column=Column(Text))
    chapter_title: str | None = Field(default=None, sa_column=Column(Text))
    kindle_location: str | None = Field(default=None, sa_column=Column(Text))
    import_source: str | None = Field(default=None, sa_column=Column(Text))
    extracted_text: str = Field(sa_column=Column(Text, nullable=False))
    color: str = Field(
        default="yellow",
        sa_column=Column(Text, nullable=False, server_default=text("'yellow'")),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    fts: str | None = Field(
        default=None,
        sa_column=Column(
            TSVECTOR,
            Computed("to_tsvector('english', extracted_text)", persisted=True),
        ),
    )


class Note(SQLModel, table=True):
    __tablename__ = "notes"
    __table_args__ = (
        Index("idx_notes_document", "document_id"),
        Index("idx_notes_highlight", "highlight_id"),
        Index("idx_notes_fts", "fts", postgresql_using="gin"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    document_id: UUID = Field(
        sa_column=Column(
            ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    highlight_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("highlights.id", ondelete="CASCADE")),
    )
    content: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )
    fts: str | None = Field(
        default=None,
        sa_column=Column(
            TSVECTOR,
            Computed("to_tsvector('english', content)", persisted=True),
        ),
    )


class Embedding(SQLModel, table=True):
    __tablename__ = "embeddings"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('page', 'highlight', 'note')",
            name="ck_embeddings_source_type",
        ),
        UniqueConstraint(
            "source_type",
            "source_id",
            name="uq_embeddings_source",
        ),
        Index(
            "idx_embeddings_vector",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_type: str = Field(sa_column=Column(String, nullable=False))
    source_id: UUID = Field(nullable=False)
    embedding: list[float] = Field(sa_column=Column(Vector(768), nullable=False))
    model: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "job_type IN ('extract_text', 'generate_embedding', 'ocr')",
            name="ck_jobs_job_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_jobs_status",
        ),
        Index(
            "idx_jobs_status",
            "status",
            postgresql_where=text("status IN ('pending', 'processing')"),
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    job_type: str = Field(sa_column=Column(String, nullable=False))
    status: str = Field(
        default="pending",
        sa_column=Column(
            String,
            nullable=False,
            server_default=text("'pending'"),
        ),
    )
    document_id: UUID | None = Field(
        default=None,
        sa_column=Column(ForeignKey("documents.id", ondelete="CASCADE")),
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    error_message: str | None = Field(default=None, sa_column=Column(Text))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )
    completed_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )


class ConfigEntry(SQLModel, table=True):
    __tablename__ = "config"

    key: str = Field(sa_column=Column(Text, primary_key=True))
    value: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
            onupdate=func.now(),
        ),
    )


class Entity(SQLModel, table=True):
    __tablename__ = "entities"
    __table_args__ = (
        CheckConstraint(
            "type IN ('book', 'concept', 'author', 'theme')",
            name="ck_entities_type",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(sa_column=Column(Text, nullable=False))
    type: str = Field(sa_column=Column(String, nullable=False))
    properties: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSONB,
            nullable=False,
            server_default=text("'{}'::jsonb"),
        ),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
            server_default=func.now(),
        ),
    )


class Triple(SQLModel, table=True):
    __tablename__ = "triples"
    __table_args__ = (
        Index("idx_triples_subject", "subject_id"),
        Index("idx_triples_object", "object_id"),
        Index("idx_triples_predicate", "predicate"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    subject_id: UUID = Field(foreign_key="entities.id", nullable=False)
    predicate: str = Field(sa_column=Column(Text, nullable=False))
    object_id: UUID = Field(foreign_key="entities.id", nullable=False)
    valid_from: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    valid_to: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True)),
    )
    source_note_id: UUID | None = Field(default=None, foreign_key="notes.id")
    confidence: float = Field(
        default=1.0,
        sa_column=Column(Float, nullable=False, server_default=text("1.0")),
    )
