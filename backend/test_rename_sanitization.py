import json
import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, call

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


class ScalarsResult:
    """Mimics the object returned by db.execute(...).scalars().all()."""
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class DummyResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        # For non-folder files there are no descendants.
        return []


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


def make_db(file_obj: SimpleNamespace, children=None):
    """Return a mock db whose first execute() yields *file_obj* and whose
    subsequent execute() calls yield an empty children list (or *children*)."""
    db = SimpleNamespace()
    children_result = ScalarsResult(children or [])
    call_count = 0

    async def fake_execute(stmt):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return DummyResult(file_obj)
        return children_result

    db.execute = fake_execute
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

    def test_rejects_name_with_slash(self):
        with self.assertRaises(HTTPException) as ctx:
            sanitize_rename_target("project/notes.txt")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_rejects_name_with_newline(self):
        with self.assertRaises(HTTPException) as ctx:
            sanitize_rename_target("bad\nname.txt")
        self.assertEqual(ctx.exception.status_code, 400)

    def test_rejects_name_with_leading_space(self):
        with self.assertRaises(HTTPException) as ctx:
            sanitize_rename_target(" leading.txt")
        self.assertEqual(ctx.exception.status_code, 400)

    async def test_file_rename_accepts_valid_name(self):
        file_obj = make_file("old.txt")
        db = make_db(file_obj)
        current_user = SimpleNamespace(id="user-1")

        response = await update_file(
            request=make_request(),
            file_id=file_obj.id,
            update=FileUpdate(name="new-name.txt"),
            current_user=current_user,
            db=db,
        )

        self.assertEqual(file_obj.name, "new-name.txt")
        self.assertEqual(response.name, "new-name.txt")
        self.assertEqual(db.add.call_count, 1)
        activity = db.add.call_args.args[0]
        self.assertEqual(activity.action, "rename")
        self.assertIn("new-name.txt", activity.file_name)

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

    async def test_file_rename_rejects_slash_in_name(self):
        file_obj = make_file("old.txt")
        db = make_db(file_obj)
        current_user = SimpleNamespace(id="user-1")

        with self.assertRaises(HTTPException) as ctx:
            await update_file(
                request=make_request(),
                file_id=file_obj.id,
                update=FileUpdate(name="project/notes.txt"),
                current_user=current_user,
                db=db,
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(file_obj.name, "old.txt")

    async def test_folder_rename_rejects_control_characters(self):
        folder = make_file("Quarterly", file_type="folder")
        db = make_db(folder)
        current_user = SimpleNamespace(id="user-1")

        with self.assertRaises(HTTPException) as ctx:
            await update_file(
                request=make_request(),
                file_id=folder.id,
                update=FileUpdate(name="FY2026/Reports\r\n"),
                current_user=current_user,
                db=db,
            )

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(folder.name, "Quarterly")

    async def test_folder_rename_valid_name(self):
        folder = make_file("Quarterly", file_type="folder")
        db = make_db(folder)
        current_user = SimpleNamespace(id="user-1")

        response = await update_file(
            request=make_request(),
            file_id=folder.id,
            update=FileUpdate(name="AnnualReports"),
            current_user=current_user,
            db=db,
        )

        self.assertEqual(folder.name, "AnnualReports")
        self.assertEqual(response.name, "AnnualReports")

    async def test_folder_rename_cascades_to_descendants(self):
        """Renaming a folder should update the path of its children."""
        folder = make_file("OldName", file_type="folder")
        folder.path = "[]"

        child = make_file("child.txt")
        child.path = '["OldName"]'

        grandchild = make_file("gc.txt")
        grandchild.path = '["OldName","sub"]'

        db = make_db(folder, children=[child, grandchild])
        current_user = SimpleNamespace(id="user-1")

        await update_file(
            request=make_request(),
            file_id=folder.id,
            update=FileUpdate(name="NewName"),
            current_user=current_user,
            db=db,
        )

        self.assertEqual(folder.name, "NewName")
        self.assertEqual(json.loads(child.path), ["NewName"])
        self.assertEqual(json.loads(grandchild.path), ["NewName", "sub"])


if __name__ == "__main__":
    unittest.main()
