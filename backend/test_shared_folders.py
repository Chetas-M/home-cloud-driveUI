import os
import shutil
import unittest
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.database import Base  # noqa: E402
from app.models import File as FileModel, SharedFolderAccess, User  # noqa: E402
from app.routers.files import list_files  # noqa: E402
from app.routers.folders import create_folder  # noqa: E402
from app.routers.shared_folders import invite_to_shared_folder, list_shared_folders  # noqa: E402
from app.schemas import FolderCreate, SharedFolderInviteCreate  # noqa: E402


TEST_DB_ROOT = os.path.join(os.path.dirname(__file__), "_tmp_shared_folder_tests")
os.makedirs(TEST_DB_ROOT, exist_ok=True)


def make_user(email: str, username: str) -> User:
    return User(email=email, username=username, password_hash="hashed", storage_quota=1024 * 1024)


class SharedFolderTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = os.path.join(TEST_DB_ROOT, f"db-{uuid.uuid4()}")
        os.makedirs(self.test_dir, exist_ok=True)
        self.database_url = f"sqlite+aiosqlite:///{os.path.join(self.test_dir, 'shared.db')}"
        self.engine = create_async_engine(self.database_url, future=True)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with self.session_factory() as db:
            self.owner = make_user("owner@example.com", "owner")
            self.viewer = make_user("viewer@example.com", "viewer")
            self.editor = make_user("editor@example.com", "editor")
            db.add_all([self.owner, self.viewer, self.editor])
            await db.flush()

            self.root_folder = FileModel(
                name="Projects",
                type="folder",
                size=0,
                path="[]",
                owner_id=self.owner.id,
                version=1,
            )
            self.child_folder = FileModel(
                name="Roadmap",
                type="folder",
                size=0,
                path='["Projects"]',
                owner_id=self.owner.id,
                version=1,
            )
            db.add_all([self.root_folder, self.child_folder])
            await db.commit()

    async def asyncTearDown(self):
        await self.engine.dispose()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_owner_can_invite_by_email_and_list_shared_root(self):
        async with self.session_factory() as db:
            access = await invite_to_shared_folder(
                folder_id=self.root_folder.id,
                payload=SharedFolderInviteCreate(identifier=self.viewer.email, role="viewer"),
                current_user=self.owner,
                db=db,
            )
            self.assertEqual(access.username, self.viewer.username)
            self.assertEqual(access.role, "viewer")

            roots = await list_shared_folders(current_user=self.viewer, db=db)
            self.assertEqual(len(roots), 1)
            self.assertTrue(roots[0].is_shared_root)
            self.assertEqual(roots[0].owner_username, self.owner.username)

    async def test_editor_can_create_folder_inside_shared_root_and_list_relative_paths(self):
        async with self.session_factory() as db:
            db.add(SharedFolderAccess(
                folder_id=self.root_folder.id,
                owner_id=self.owner.id,
                user_id=self.editor.id,
                role="editor",
            ))
            await db.commit()

        async with self.session_factory() as db:
            created = await create_folder(
                folder=FolderCreate(name="Specs", path=[], shared_folder_id=self.root_folder.id),
                current_user=self.editor,
                db=db,
            )
            self.assertEqual(created.path, [])
            self.assertEqual(created.access_role, "editor")

            items = await list_files(
                path="[]",
                include_trashed=False,
                starred_only=False,
                shared_folder_id=self.root_folder.id,
                current_user=self.editor,
                db=db,
            )
            names = {item.name: item.path for item in items}
            self.assertIn("Roadmap", names)
            self.assertIn("Specs", names)
            self.assertEqual(names["Roadmap"], [])
            self.assertEqual(names["Specs"], [])

    async def test_viewer_cannot_create_folder_inside_shared_root(self):
        async with self.session_factory() as db:
            db.add(SharedFolderAccess(
                folder_id=self.root_folder.id,
                owner_id=self.owner.id,
                user_id=self.viewer.id,
                role="viewer",
            ))
            await db.commit()

        async with self.session_factory() as db:
            with self.assertRaises(HTTPException) as ctx:
                await create_folder(
                    folder=FolderCreate(name="Specs", path=[], shared_folder_id=self.root_folder.id),
                    current_user=self.viewer,
                    db=db,
                )

            self.assertEqual(ctx.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
