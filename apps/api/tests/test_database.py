import tempfile
import unittest
from pathlib import Path

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
                    "fields": {"title": "Alpha", "doi": "10.1/alpha"},
                    "notes": "read",
                },
                {
                    "key": "beta",
                    "entry_type": "book",
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
        db.upsert_entry({"key": "one", "entry_type": "misc", "title": "One"})
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


if __name__ == "__main__":
    unittest.main()
