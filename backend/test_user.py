import os
import shutil
import unittest
import uuid

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.auth import get_password_hash  # noqa: E402
from app.database import Base  # noqa: E402
from app.models import User  # noqa: E402


TEST_DB_ROOT = os.path.join(os.path.dirname(__file__), "_tmp_db_tests")
os.makedirs(TEST_DB_ROOT, exist_ok=True)


class UserPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = os.path.join(TEST_DB_ROOT, f"db-{uuid.uuid4()}")
        os.makedirs(self.test_dir, exist_ok=True)
        self.database_url = f"sqlite+aiosqlite:///{os.path.join(self.test_dir, 'users.db')}"
        self.engine = create_async_engine(self.database_url, future=True)
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_create_user(self):
        async with self.session_factory() as db:
            new_user = User(
                email="test3@example.com",
                username="testuser3",
                password_hash=get_password_hash("password123"),
                storage_quota=107374182400,
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)

        self.assertIsNotNone(new_user.id)
        self.assertEqual(new_user.email, "test3@example.com")
        self.assertEqual(new_user.username, "testuser3")


if __name__ == "__main__":
    unittest.main()
