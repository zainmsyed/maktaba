from __future__ import annotations

import os
import unittest

from sqlalchemy import create_engine, inspect, text

REQUIRED_TABLES = {
    "config",
    "documents",
    "embeddings",
    "entities",
    "folders",
    "highlights",
    "jobs",
    "notes",
    "pages",
    "triples",
}

EXPECTED_FK_ONDELETE = {
    "pages": {("document_id",): "CASCADE"},
    "highlights": {("document_id",): "CASCADE"},
    "notes": {
        ("document_id",): "CASCADE",
        ("highlight_id",): "CASCADE",
    },
    "jobs": {("document_id",): "CASCADE"},
    "documents": {("folder_id",): "SET NULL"},
}

EXPECTED_HIGHLIGHT_COLUMNS = {"highlight_type", "rects"}

EXPECTED_INDEX_SNIPPETS = {
    "idx_documents_deleted": ["USING btree", "deleted_at", "WHERE", "deleted_at IS NULL"],
    "idx_documents_folder": ["USING btree", "folder_id"],
    "idx_jobs_status": ["USING btree", "status", "WHERE", "pending", "processing"],
    "idx_notes_fts": ["USING gin", "fts"],
    "idx_highlights_fts": ["USING gin", "fts"],
    "idx_embeddings_vector": ["USING ivfflat", "vector_cosine_ops"],
}


class SchemaSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise unittest.SkipTest("DATABASE_URL is required for schema smoke tests")

        cls.engine = create_engine(database_url)
        cls.inspector = inspect(cls.engine)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def test_vector_extension_is_enabled(self) -> None:
        with self.engine.connect() as connection:
            enabled = connection.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')",
                ),
            ).scalar_one()

        self.assertTrue(enabled)

    def test_required_tables_exist(self) -> None:
        table_names = set(self.inspector.get_table_names(schema="public"))
        self.assertTrue(REQUIRED_TABLES.issubset(table_names))

    def test_ownership_foreign_keys_use_cascade(self) -> None:
        for table_name, expected_constraints in EXPECTED_FK_ONDELETE.items():
            foreign_keys = {
                tuple(foreign_key["constrained_columns"]): (
                    (foreign_key.get("options") or {}).get("ondelete")
                )
                for foreign_key in self.inspector.get_foreign_keys(table_name, schema="public")
            }
            self.assertEqual(expected_constraints, foreign_keys)

    def test_highlight_locator_columns_exist(self) -> None:
        column_names = {
            column["name"]
            for column in self.inspector.get_columns("highlights", schema="public")
        }
        self.assertTrue(EXPECTED_HIGHLIGHT_COLUMNS.issubset(column_names))

    def test_critical_index_definitions_exist(self) -> None:
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'public'",
                ),
            )
            index_definitions = {row.indexname: row.indexdef for row in rows}

        for index_name, snippets in EXPECTED_INDEX_SNIPPETS.items():
            self.assertIn(index_name, index_definitions)
            index_definition = index_definitions[index_name]
            for snippet in snippets:
                self.assertIn(snippet, index_definition)


if __name__ == "__main__":
    unittest.main()
