import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fastapi import HTTPException
from starlette.requests import Request

os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.routers.files import sanitize_rename_target, update_file  # noqa: E402
from app.schemas import FileUpdate  # noqa: E402


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "PATCH",
            "scheme": "http",
            "path": "/api/files/file-1",
            "headers": [(b"host", b"testserver")],
            "server": ("testserver", 80),
        }
    )


class DummyResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


def make_file(name: str, file_type: str = "file") -> SimpleNamespace:
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id="file-1",
        name=name,
        type=file_type,
        mime_type="text/plain" if file_type != "folder" else None,
        size=1 if file_type != "folder" else 0,
        path="[]",
        is_starred=False,
        is_trashed=False,
        thumbnail_path=None,
        version=1,
        created_at=now,
        updated_at=now,
    )


def make_db(file_obj: SimpleNamespace):
    db = SimpleNamespace()
    db.execute = AsyncMock(return_value=DummyResult(file_obj))
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


class RenameSanitizationTests(unittest.IsolatedAsyncioTestCase):
    def test_rejects_names_that_collapse_to_empty(self):
        with self.assertRaises(HTTPException) as ctx:
            sanitize_rename_target(" \u202e..\x00 ")

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail, "File/folder name is invalid")

    def test_allows_literal_unnamed(self):
        self.assertEqual(sanitize_rename_target("unnamed"), "unnamed")

    async def test_file_rename_sanitizes_problematic_characters(self):
        file_obj = make_file("old.txt")
        db = make_db(file_obj)
        current_user = SimpleNamespace(id="user-1")

        response = await update_file(
            request=make_request(),
            file_id=file_obj.id,
            update=FileUpdate(name="project/\nnotes.txt"),
            current_user=current_user,
            db=db,
        )

        self.assertEqual(file_obj.name, "project__notes.txt")
        self.assertEqual(response.name, "project__notes.txt")
        self.assertEqual(db.add.call_count, 1)
        activity = db.add.call_args.args[0]
        self.assertEqual(activity.action, "rename")
        self.assertIn("project__notes.txt", activity.file_name)

    async def test_folder_rename_uses_the_same_rules(self):
        folder = make_file("Quarterly", file_type="folder")
        db = make_db(folder)
        current_user = SimpleNamespace(id="user-1")

        response = await update_file(
            request=make_request(),
            file_id=folder.id,
            update=FileUpdate(name="FY2026/Reports\r\n"),
            current_user=current_user,
            db=db,
        )

        self.assertEqual(folder.name, "FY2026_Reports__")
        self.assertEqual(response.name, "FY2026_Reports__")

    async def test_rename_rejects_invalid_names_without_mutating_file(self):
        file_obj = make_file("keep.txt")
        db = make_db(file_obj)
        current_user = SimpleNamespace(id="user-1")

        with self.assertRaises(HTTPException) as ctx:
            await update_file(
                request=make_request(),
                file_id=file_obj.id,
                update=FileUpdate(name=" \u202e..\x00 "),
                current_user=current_user,
                db=db,
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(file_obj.name, "keep.txt")
        db.add.assert_not_called()
        db.flush.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
