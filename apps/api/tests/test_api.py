import os
import tempfile
import unittest
from pathlib import Path

import main
from fastapi.testclient import TestClient
from services import database as db
from services.source_asset_storage import get_source_asset_storage


class FakeSourceAssetStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[int, str]] = {}

    def presign_upload(
        self,
        *,
        storage_key: str,
        media_type: str,
        byte_size: int,
        sha256: str,
    ) -> tuple[str, dict[str, str]]:
        return (
            f"https://private-r2.test/upload/{storage_key}",
            {
                "Content-Type": media_type,
                "x-amz-meta-sha256": sha256,
                "x-amz-meta-byte-size": str(byte_size),
            },
        )

    def verify_object(self, *, storage_key: str, byte_size: int, sha256: str) -> bool:
        return self.objects.get(storage_key) == (byte_size, sha256)

    def presign_get(
        self,
        *,
        storage_key: str,
        filename: str,
        disposition: str,
    ) -> str:
        return (
            f"https://private-r2.test/access/{storage_key}"
            f"?disposition={disposition}&filename={filename}"
        )


class DatabaseApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.original_database_url = db.DATABASE_URL
        self.original_paths = (db.BIB_PATH, db.LEGACY_NOTES_PATH)
        self.original_sync_token = os.environ.get("BIB_SYNC_TOKEN")
        self.original_admin_token = os.environ.get("BIB_ADMIN_TOKEN")
        self.original_session_secret = os.environ.get("BIB_SESSION_SECRET")
        os.environ["BIB_SYNC_TOKEN"] = "test-sync-token"
        os.environ["BIB_ADMIN_TOKEN"] = "test-admin-password"
        os.environ["BIB_SESSION_SECRET"] = "test-session-secret-with-32-bytes"
        db.configure_database(f"sqlite:///{root / 'library.sqlite3'}")
        db.BIB_PATH = root / "bibliography.bib"
        db.LEGACY_NOTES_PATH = root / "notes.toon"
        self.storage = FakeSourceAssetStorage()
        main.app.dependency_overrides[get_source_asset_storage] = lambda: self.storage
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        main.app.dependency_overrides.clear()
        db.BIB_PATH, db.LEGACY_NOTES_PATH = self.original_paths
        db.configure_database(self.original_database_url)
        if self.original_sync_token is None:
            os.environ.pop("BIB_SYNC_TOKEN", None)
        else:
            os.environ["BIB_SYNC_TOKEN"] = self.original_sync_token
        if self.original_admin_token is None:
            os.environ.pop("BIB_ADMIN_TOKEN", None)
        else:
            os.environ["BIB_ADMIN_TOKEN"] = self.original_admin_token
        if self.original_session_secret is None:
            os.environ.pop("BIB_SESSION_SECRET", None)
        else:
            os.environ["BIB_SESSION_SECRET"] = self.original_session_secret
        self.temporary_directory.cleanup()

    def test_public_entry_only_projects_pdf_availability(self) -> None:
        self.client.post(
            "/api/entries",
            json={
                "key": "private-source",
                "entry_type": "article",
                "academic_fields": ["philosophy"],
                "title": "Private Source",
            },
        ).raise_for_status()

        without_pdf = self.client.get("/api/entries/private-source").json()
        self.assertIs(without_pdf["has_pdf"], False)

        asset = db.create_source_asset(
            entry_key="private-source",
            kind="published-pdf",
            filename="private.pdf",
            media_type="application/pdf",
            byte_size=128,
            sha256="a" * 64,
            storage_key="bibliography/private-source/asset/private.pdf",
        )
        db.mark_source_asset_ready(asset["id"])

        public_entry = self.client.get("/api/entries/private-source").json()
        self.assertIs(public_entry["has_pdf"], True)
        self.assertNotIn("assets", public_entry)
        self.assertNotIn("storage_key", public_entry)
        listed_entry = self.client.get("/api/entries?per_page=200").json()["entries"][0]
        self.assertIs(listed_entry["has_pdf"], True)
        self.assertNotIn("assets", listed_entry)

    def test_admin_session_is_independent_and_required_for_assets(self) -> None:
        invalid = self.client.post("/api/admin/session", json={"credential": "wrong"})
        self.assertEqual(invalid.status_code, 401)

        session = self.client.post(
            "/api/admin/session",
            json={"credential": "test-admin-password"},
        )
        self.assertEqual(session.status_code, 200)
        session_payload = session.json()
        self.assertIn("token", session_payload)
        self.assertIn("expires_at", session_payload)
        self.assertNotIn("test-admin-password", session.text)

        self.client.post(
            "/api/entries",
            json={
                "key": "protected-assets",
                "academic_fields": ["philosophy"],
                "title": "Protected Assets",
            },
        ).raise_for_status()
        without_session = self.client.get("/api/admin/entries/protected-assets/assets")
        self.assertEqual(without_session.status_code, 401)
        sync_token = self.client.get(
            "/api/admin/entries/protected-assets/assets",
            headers={"Authorization": "Bearer test-sync-token"},
        )
        self.assertEqual(sync_token.status_code, 401)
        authorized = self.client.get(
            "/api/admin/entries/protected-assets/assets",
            headers={"Authorization": f"Bearer {session_payload['token']}"},
        )
        self.assertEqual(authorized.status_code, 200)
        self.assertEqual(authorized.json(), {"assets": []})

    def test_private_asset_upload_completion_and_access_lifecycle(self) -> None:
        self.client.post(
            "/api/entries",
            json={
                "key": "asset-lifecycle",
                "entry_type": "article",
                "academic_fields": ["philosophy"],
                "title": "Asset Lifecycle",
            },
        ).raise_for_status()
        session = self.client.post(
            "/api/admin/session",
            json={"credential": "test-admin-password"},
        ).json()
        headers = {"Authorization": f"Bearer {session['token']}"}
        payload = {
            "kind": "published-pdf",
            "filename": "published paper.pdf",
            "media_type": "application/pdf",
            "byte_size": 512,
            "sha256": "b" * 64,
            "source_url": "https://example.com/published.pdf",
        }

        upload = self.client.post(
            "/api/admin/entries/asset-lifecycle/assets/uploads",
            headers=headers,
            json=payload,
        )
        self.assertEqual(upload.status_code, 200)
        upload_payload = upload.json()
        self.assertIs(upload_payload["deduplicated"], False)
        self.assertEqual(upload_payload["asset"]["status"], "pending")
        self.assertTrue(
            upload_payload["upload_url"].startswith("https://private-r2.test/upload/")
        )
        self.assertEqual(
            upload_payload["upload_headers"]["x-amz-meta-sha256"],
            "b" * 64,
        )
        self.assertIs(
            self.client.get("/api/entries/asset-lifecycle").json()["has_pdf"],
            False,
        )

        asset = upload_payload["asset"]
        self.storage.objects[asset["storage_key"]] = (
            asset["byte_size"],
            asset["sha256"],
        )
        completed = self.client.post(
            f"/api/admin/assets/{asset['id']}/complete",
            headers=headers,
        )
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["status"], "ready")
        self.assertIs(
            self.client.get("/api/entries/asset-lifecycle").json()["has_pdf"],
            True,
        )

        preferred = self.client.get(
            "/api/admin/entries/asset-lifecycle/preferred-pdf/access",
            headers=headers,
        )
        self.assertEqual(preferred.status_code, 200)
        self.assertIn("disposition=inline", preferred.json()["url"])
        self.assertIn("expires_at", preferred.json())

        download = self.client.get(
            f"/api/admin/assets/{asset['id']}/access?disposition=attachment",
            headers=headers,
        )
        self.assertEqual(download.status_code, 200)
        self.assertIn("disposition=attachment", download.json()["url"])

        duplicate = self.client.post(
            "/api/admin/entries/asset-lifecycle/assets/uploads",
            headers=headers,
            json={**payload, "kind": "author-manuscript-pdf"},
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertIs(duplicate.json()["deduplicated"], True)
        self.assertIsNone(duplicate.json()["upload_url"])
        self.assertEqual(duplicate.json()["asset"]["id"], asset["id"])

    def test_upload_completion_fails_closed_when_object_does_not_match(self) -> None:
        self.client.post(
            "/api/entries",
            json={
                "key": "mismatch",
                "academic_fields": ["philosophy"],
                "title": "Mismatch",
            },
        ).raise_for_status()
        session = self.client.post(
            "/api/admin/session",
            json={"credential": "test-admin-password"},
        ).json()
        headers = {"Authorization": f"Bearer {session['token']}"}
        upload = self.client.post(
            "/api/admin/entries/mismatch/assets/uploads",
            headers=headers,
            json={
                "kind": "published-pdf",
                "filename": "mismatch.pdf",
                "media_type": "application/pdf",
                "byte_size": 12,
                "sha256": "c" * 64,
            },
        ).json()

        response = self.client.post(
            f"/api/admin/assets/{upload['asset']['id']}/complete",
            headers=headers,
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            db.get_source_asset(upload["asset"]["id"])["status"],
            "failed",
        )
        self.assertIs(
            self.client.get("/api/entries/mismatch").json()["has_pdf"],
            False,
        )

        retry = self.client.post(
            "/api/admin/entries/mismatch/assets/uploads",
            headers=headers,
            json={
                "kind": "published-pdf",
                "filename": "mismatch.pdf",
                "media_type": "application/pdf",
                "byte_size": 12,
                "sha256": "c" * 64,
            },
        )
        self.assertEqual(retry.status_code, 200)
        self.assertIs(retry.json()["deduplicated"], True)
        self.assertIsNotNone(retry.json()["upload_url"])
        self.assertEqual(retry.json()["asset"]["status"], "pending")

    def test_publication_sync_attaches_blog_posts(self) -> None:
        self.client.post(
            "/api/entries",
            json={
                "key": "fine1994",
                "entry_type": "article",
                "academic_fields": ["philosophy"],
                "title": "Essence and Modality",
            },
        ).raise_for_status()
        headers = {"Authorization": "Bearer test-sync-token"}
        blog_response = self.client.post(
            "/api/sync/blog-posts",
            headers=headers,
            json={
                "posts": [
                    {
                        "slug": "phlosophy/metaphysic/essence-and-modality",
                        "title": "Kit Fine, Essence and Modality",
                        "url": "https://wayneh.tw/posts/phlosophy/metaphysic/essence-and-modality",
                        "source_path": (
                            "src/content/posts/phlosophy/metaphysic/"
                            "essence-and-modality.md"
                        ),
                        "published_at": "2026-01-01T00:00:00Z",
                        "bib_keys": ["fine1994"],
                    }
                ]
            },
        )
        self.assertEqual(blog_response.status_code, 200)

        entry = self.client.get("/api/entries/fine1994").json()
        self.assertEqual(
            entry["blog_posts"][0]["slug"],
            "phlosophy/metaphysic/essence-and-modality",
        )

    def test_publication_sync_requires_token_and_known_keys(self) -> None:
        unauthorized = self.client.post("/api/sync/blog-posts", json={"posts": []})
        self.assertEqual(unauthorized.status_code, 401)
        unknown = self.client.post(
            "/api/sync/blog-posts",
            headers={"Authorization": "Bearer test-sync-token"},
            json={
                "posts": [
                    {
                        "slug": "missing",
                        "title": "Missing",
                        "url": "https://example.com/missing",
                        "source_path": "missing.md",
                        "bib_keys": ["missing"],
                    }
                ]
            },
        )
        self.assertEqual(unknown.status_code, 400)

    def test_selected_save_and_database_derived_export(self) -> None:
        response = self.client.post(
            "/api/entries/batch",
            json={
                "entries": [
                    {
                        "key": "kripke1959",
                        "entry_type": "article",
                        "academic_fields": ["philosophy"],
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

        export = self.client.post("/api/entries/export", json={"keys": ["kripke1959"]})
        self.assertEqual(export.status_code, 200)
        self.assertIn("@article{kripke1959", export.json()["content"])

    def test_entry_academic_fields_are_required_normalized_and_returned(self) -> None:
        missing = self.client.post(
            "/api/entries",
            json={"key": "unclassified", "fields": {"title": "Unclassified"}},
        )
        self.assertEqual(missing.status_code, 422)

        invalid = self.client.post(
            "/api/entries",
            json={
                "key": "invalid-field",
                "academic_fields": ["Philosophy"],
                "fields": {"title": "Invalid"},
            },
        )
        self.assertEqual(invalid.status_code, 422)

        saved = self.client.post(
            "/api/entries",
            json={
                "key": "interdisciplinary",
                "academic_fields": [
                    "philosophy",
                    "computer-science",
                    "philosophy",
                ],
                "fields": {"title": "Interdisciplinary"},
            },
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(
            saved.json()["academic_fields"],
            ["philosophy", "computer-science"],
        )
        self.assertEqual(
            self.client.get("/api/entries/interdisciplinary").json()["academic_fields"],
            ["philosophy", "computer-science"],
        )

    def test_sync_alias_only_exports_database_to_bibtex(self) -> None:
        self.client.post(
            "/api/entries",
            json={
                "key": "db-first",
                "academic_fields": ["philosophy"],
                "fields": {"title": "Canonical"},
            },
        )
        response = self.client.post("/api/cli/sync")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["direction"], "database-to-bibtex")
        self.assertIn("db-first", db.BIB_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
