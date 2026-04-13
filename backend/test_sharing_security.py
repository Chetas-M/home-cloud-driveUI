import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.models import ShareLink, File as FileModel  # noqa: E402
from app.routers.sharing import (  # noqa: E402
    reserve_share_download_slot,
    create_share_link,
    access_shared_file,
    _deactivate_share_link_for_trashed_file,
)
from app.schemas import ShareLinkCreate  # noqa: E402


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/api/share",
            "headers": [(b"host", b"testserver"), (b"x-forwarded-for", b"127.0.0.1")],
            "server": ("testserver", 80),
        }
    )


def make_file(is_trashed: bool = False, file_type: str = "file") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id="file-1",
        owner_id="user-1",
        name="test.txt",
        type=file_type,
        mime_type="text/plain",
        size=42,
        storage_path=None,
        path="[]",
        is_trashed=is_trashed,
        is_starred=False,
        thumbnail_path=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


class ShareLinkSchemaTests(unittest.TestCase):
    def test_rejects_unknown_permission(self):
        with self.assertRaises(ValidationError):
            ShareLinkCreate(file_id="file-1", permission="edit")

    def test_rejects_non_positive_max_downloads(self):
        with self.assertRaises(ValidationError):
            ShareLinkCreate(file_id="file-1", permission="download", max_downloads=0)


class ShareDownloadSlotTests(unittest.IsolatedAsyncioTestCase):
    async def test_raises_when_no_capped_download_slots_remain(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=Mock(rowcount=0))
        db.flush = AsyncMock()
        link = ShareLink(id="link-1", max_downloads=1)

        with self.assertRaises(HTTPException) as ctx:
            await reserve_share_download_slot(db, link)

        self.assertEqual(ctx.exception.status_code, 410)
        db.flush.assert_not_awaited()

    async def test_unlimited_links_increment_without_cap_check(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=Mock(rowcount=1))
        db.flush = AsyncMock()
        link = ShareLink(id="link-1", max_downloads=None)

        await reserve_share_download_slot(db, link)

        db.flush.assert_awaited_once()


class CreateShareLinkTrashedFileTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_400_when_file_is_trashed(self):
        """create_share_link must reject files that are in the trash."""
        trashed_file = make_file(is_trashed=True)
        db = AsyncMock()
        db.execute = AsyncMock(return_value=Mock(scalar_one_or_none=Mock(return_value=trashed_file)))
        current_user = SimpleNamespace(id="user-1")

        with self.assertRaises(HTTPException) as ctx:
            await create_share_link(
                request=make_request(),
                data=ShareLinkCreate(file_id="file-1", permission="view"),
                current_user=current_user,
                db=db,
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("trash", ctx.exception.detail.lower())

    async def test_returns_400_when_sharing_folder(self):
        """create_share_link must reject folder shares."""
        folder = make_file(file_type="folder")
        db = AsyncMock()
        db.execute = AsyncMock(return_value=Mock(scalar_one_or_none=Mock(return_value=folder)))
        current_user = SimpleNamespace(id="user-1")

        with self.assertRaises(HTTPException) as ctx:
            await create_share_link(
                request=make_request(),
                data=ShareLinkCreate(file_id="file-1", permission="view"),
                current_user=current_user,
                db=db,
            )

        self.assertEqual(ctx.exception.status_code, 400)

    async def test_returns_404_when_file_not_found(self):
        db = AsyncMock()
        db.execute = AsyncMock(return_value=Mock(scalar_one_or_none=Mock(return_value=None)))
        current_user = SimpleNamespace(id="user-1")

        with self.assertRaises(HTTPException) as ctx:
            await create_share_link(
                request=make_request(),
                data=ShareLinkCreate(file_id="missing", permission="view"),
                current_user=current_user,
                db=db,
            )

        self.assertEqual(ctx.exception.status_code, 404)


class AccessSharedFileTrashedTests(unittest.IsolatedAsyncioTestCase):
    def _make_link(self, is_active: bool = True) -> ShareLink:
        now = datetime.now(timezone.utc)
        link = ShareLink(id="link-1", file_id="file-1", owner_id="user-1")
        link.is_active = is_active
        link.password_hash = None
        link.expires_at = None
        link.max_downloads = None
        link.download_count = 0
        link.permission = "view"
        return link

    async def test_access_shared_file_returns_410_when_file_is_trashed(self):
        """Accessing a share link for a trashed file must return 410."""
        trashed_file = make_file(is_trashed=True)
        link = self._make_link()

        row_mock = Mock()
        row_mock.__getitem__ = Mock(side_effect=lambda i: link if i == 0 else trashed_file)
        result_mock = Mock()
        result_mock.first = Mock(return_value=row_mock)

        db = AsyncMock()
        db.execute = AsyncMock(return_value=result_mock)
        db.commit = AsyncMock()

        with self.assertRaises(HTTPException) as ctx:
            await access_shared_file(
                request=make_request(),
                token="test-token",
                body=None,
                db=db,
            )

        self.assertEqual(ctx.exception.status_code, 410)

    async def test_access_shared_file_deactivates_link_when_file_is_trashed(self):
        """When the file is trashed, the share link must be deactivated."""
        trashed_file = make_file(is_trashed=True)
        link = self._make_link(is_active=True)

        row_mock = Mock()
        row_mock.__getitem__ = Mock(side_effect=lambda i: link if i == 0 else trashed_file)
        result_mock = Mock()
        result_mock.first = Mock(return_value=row_mock)

        db = AsyncMock()
        db.execute = AsyncMock(return_value=result_mock)
        db.commit = AsyncMock()

        with self.assertRaises(HTTPException):
            await access_shared_file(
                request=make_request(),
                token="test-token",
                body=None,
                db=db,
            )

        # The link should have been deactivated in the DB.
        self.assertFalse(link.is_active)
        db.commit.assert_awaited()

    async def test_deactivate_helper_is_idempotent_for_already_inactive_links(self):
        """_deactivate_share_link_for_trashed_file should be a no-op when link is already
        inactive."""
        link = self._make_link(is_active=False)
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()

        await _deactivate_share_link_for_trashed_file(db, link)

        db.execute.assert_not_awaited()
        db.commit.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
