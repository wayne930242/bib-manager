import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import main
from services import database as db


class DatabaseApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.original_database_url = db.DATABASE_URL
        self.original_paths = (db.BIB_PATH, db.LEGACY_NOTES_PATH)
        db.configure_database(f"sqlite:///{root / 'library.sqlite3'}")
        db.BIB_PATH = root / "bibliography.bib"
        db.LEGACY_NOTES_PATH = root / "notes.toon"
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        db.BIB_PATH, db.LEGACY_NOTES_PATH = self.original_paths
        db.configure_database(self.original_database_url)
        self.temporary_directory.cleanup()

    def test_selected_save_and_database_derived_export(self) -> None:
        response = self.client.post(
            "/api/entries/batch",
            json={
                "entries": [
                    {
                        "key": "kripke1959",
                        "entry_type": "article",
                        "fields": {
                            "author": "Saul Kripke",
                            "title": "A Completeness Theorem in Modal Logic",
                            "year": "1959",
                        },
                    }
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["saved"], 1)

        export = self.client.post(
            "/api/entries/export", json={"keys": ["kripke1959"]}
        )
        self.assertEqual(export.status_code, 200)
        self.assertIn("@article{kripke1959", export.json()["content"])

    def test_sync_alias_only_exports_database_to_bibtex(self) -> None:
        self.client.post(
            "/api/entries",
            json={"key": "db-first", "fields": {"title": "Canonical"}},
        )
        response = self.client.post("/api/cli/sync")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["direction"], "database-to-bibtex")
        self.assertIn("db-first", db.BIB_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
