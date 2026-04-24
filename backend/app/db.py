from __future__ import annotations

import argparse
import os
from collections.abc import Generator, Sequence

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection
from sqlmodel import Session, SQLModel

from app import models  # noqa: F401 - ensure model registration for metadata

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://app:change-me@localhost:5432/maktaba",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def vector_extension_enabled(connection: Connection) -> bool:
    return bool(
        connection.exec_driver_sql(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')",
        ).scalar_one(),
    )


def create_tables(connection: Connection) -> None:
    SQLModel.metadata.create_all(connection)


def initialize_database() -> None:
    with engine.begin() as connection:
        if not vector_extension_enabled(connection):
            raise RuntimeError(
                "The current database is missing the pgvector extension. "
                "Run `python -m app.db bootstrap` with a role that can create "
                "extensions, or install the extension through your normal "
                "database bootstrap/migration flow before starting the app.",
            )
        create_tables(connection)


def bootstrap_database() -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
        create_tables(connection)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Database bootstrap helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "bootstrap",
        help="Create required extensions and tables for a new database",
    )
    subparsers.add_parser(
        "init",
        help="Validate required extensions and create tables without privileged DDL",
    )

    args = parser.parse_args(argv)

    if args.command == "bootstrap":
        bootstrap_database()
    elif args.command == "init":
        initialize_database()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
