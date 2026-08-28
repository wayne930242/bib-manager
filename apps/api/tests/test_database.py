import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config
from services import database as db


class DatabaseFirstTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.original_database_url = db.DATABASE_URL
        self.original_paths = (db.BIB_PATH, db.LEGACY_NOTES_PATH)
        (self.root / "data").mkdir()
        db.configure_database(f"sqlite:///{self.root / 'data' / 'library.sqlite3'}")
        db.BIB_PATH = self.root / "references" / "bibliography.bib"
        db.LEGACY_NOTES_PATH = self.root / "legacy-notes.toon"
        db.BIB_PATH.parent.mkdir(parents=True)

    def tearDown(self) -> None:
        db.BIB_PATH, db.LEGACY_NOTES_PATH = self.original_paths
        db.configure_database(self.original_database_url)
        self.temporary_directory.cleanup()

    def test_bootstrap_import_happens_only_once(self) -> None:
        db.BIB_PATH.write_text(
            "@article{first,\n  title = {Original title},\n  year = {2025},\n}\n",
            encoding="utf-8",
        )
        db.init_db()
        self.assertEqual(db.get_entry("first")["title"], "Original title")

        db.BIB_PATH.write_text(
            "@article{first,\n  title = {Must not overwrite DB},\n}\n",
            encoding="utf-8",
        )
        db.init_db()
        self.assertEqual(db.get_entry("first")["title"], "Original title")

    def test_database_writes_and_selected_export(self) -> None:
        db.init_db()
        db.upsert_entries(
            [
                {
                    "key": "alpha",
                    "entry_type": "article",
                    "academic_fields": ["philosophy"],
                    "fields": {"title": "Alpha", "doi": "10.1/alpha"},
                    "notes": "read",
                },
                {
                    "key": "beta",
                    "entry_type": "book",
                    "academic_fields": ["philosophy"],
                    "title": "Beta",
                    "publisher": "Press",
                },
            ]
        )

        rendered = db.export_bibtex(["beta"])
        self.assertIn("@book{beta", rendered)
        self.assertIn("title = {Beta}", rendered)
        self.assertNotIn("alpha", rendered)
        self.assertEqual(db.get_entry("alpha")["notes"], "read")

    def test_export_file_is_derived_without_changing_database(self) -> None:
        db.init_db()
        db.upsert_entry(
            {
                "key": "one",
                "entry_type": "misc",
                "academic_fields": ["philosophy"],
                "title": "One",
            }
        )
        db.export_bibtex(output_path=db.BIB_PATH)
        db.BIB_PATH.write_text("@misc{tampered,}\n", encoding="utf-8")

        self.assertIsNotNone(db.get_entry("one"))
        self.assertIsNone(db.get_entry("tampered"))

    def test_duplicate_legacy_keys_are_rejected(self) -> None:
        db.BIB_PATH.write_text(
            "@misc{same, title={One}}\n@misc{same, title={Two}}\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "Duplicate citation keys"):
            db.import_bibtex(db.BIB_PATH)

    def test_academic_fields_migration_backfills_existing_entries(self) -> None:
        config = Config(str(db.API_ROOT / "alembic.ini"))
        command.upgrade(config, "20260822_01")
        now = datetime.now(UTC).isoformat()
        with db.engine.begin() as connection:
            connection.exec_driver_sql(
                """
                INSERT INTO entries (
                    key, entry_type, title, author, year, journal, publisher,
                    fields, notes, sort_order, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy-philosophy",
                    "article",
                    "Legacy",
                    "",
                    "2026",
                    "",
                    "",
                    "{}",
                    "",
                    0,
                    now,
                    now,
                ),
            )

        command.upgrade(config, "head")
        with db.engine.connect() as connection:
            row = (
                connection.exec_driver_sql(
                    "SELECT academic_fields FROM entries WHERE key = ?",
                    ("legacy-philosophy",),
                )
                .mappings()
                .one()
            )
        fields = row["academic_fields"]
        if isinstance(fields, str):
            import json

            fields = json.loads(fields)
        self.assertEqual(fields, ["philosophy"])

    def test_source_asset_lifecycle_controls_has_pdf(self) -> None:
        db.init_db()
        db.upsert_entry(
            {
                "key": "daly2023explanation",
                "entry_type": "article",
                "academic_fields": ["philosophy"],
                "title": "Explanations: Good and Bad",
            }
        )
        text_asset = db.create_source_asset(
            entry_key="daly2023explanation",
            kind="extracted-text",
            filename="paper.md",
            media_type="text/markdown",
            byte_size=40,
            sha256="1" * 64,
            storage_key="bibliography/daly2023explanation/text/paper.md",
        )
        db.mark_source_asset_ready(text_asset["id"])
        self.assertIs(db.get_entry("daly2023explanation")["has_pdf"], False)

        pdf_asset = db.create_source_asset(
            entry_key="daly2023explanation",
            kind="published-pdf",
            filename="journal.pdf",
            media_type="application/pdf",
            byte_size=210249,
            sha256="2" * 64,
            storage_key="bibliography/daly2023explanation/pdf/journal.pdf",
            source_url="https://example.com/journal.pdf",
        )
        self.assertEqual(pdf_asset["status"], "pending")
        self.assertIs(db.get_entry("daly2023explanation")["has_pdf"], False)

        ready = db.mark_source_asset_ready(pdf_asset["id"])
        self.assertEqual(ready["status"], "ready")
        self.assertIs(db.get_entry("daly2023explanation")["has_pdf"], True)
        self.assertEqual(
            db.get_preferred_pdf("daly2023explanation")["id"],
            pdf_asset["id"],
        )

        duplicate = db.create_source_asset(
            entry_key="daly2023explanation",
            kind="author-manuscript-pdf",
            filename="same-bytes.pdf",
            media_type="application/pdf",
            byte_size=210249,
            sha256="2" * 64,
            storage_key="bibliography/daly2023explanation/pdf/duplicate.pdf",
        )
        self.assertEqual(duplicate["id"], pdf_asset["id"])
        self.assertEqual(len(db.get_source_assets("daly2023explanation")), 2)

    def test_source_asset_migration_cascades_with_entry(self) -> None:
        db.init_db()
        db.upsert_entry(
            {
                "key": "temporary",
                "academic_fields": ["philosophy"],
                "title": "Temporary",
            }
        )
        db.create_source_asset(
            entry_key="temporary",
            kind="supplement",
            filename="data.txt",
            media_type="text/plain",
            byte_size=4,
            sha256="3" * 64,
            storage_key="bibliography/temporary/supplement/data.txt",
        )
        with db.engine.begin() as connection:
            connection.execute(
                db.entries_table.delete().where(db.entries_table.c.key == "temporary")
            )
        self.assertEqual(db.get_source_assets("temporary"), [])

    def test_unclassified_research_pdf_is_still_previewable(self) -> None:
        db.init_db()
        db.upsert_entry(
            {
                "key": "research-copy",
                "academic_fields": ["philosophy"],
                "title": "Research Copy",
            }
        )
        asset = db.create_source_asset(
            entry_key="research-copy",
            kind="source-document",
            filename="paper.pdf",
            media_type="application/pdf",
            byte_size=100,
            sha256="4" * 64,
            storage_key="bibliography/research-copy/source/paper.pdf",
        )
        db.mark_source_asset_ready(asset["id"])
        self.assertIs(db.get_entry("research-copy")["has_pdf"], True)
        self.assertEqual(db.get_preferred_pdf("research-copy")["id"], asset["id"])


if __name__ == "__main__":
    unittest.main()
