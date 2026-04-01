import io
import os
import shutil
import unittest
import uuid
from types import SimpleNamespace

from fastapi import HTTPException, UploadFile
from starlette.requests import Request

os.environ.setdefault("SECRET_KEY", "0123456789abcdef0123456789abcdef")

from app.routers.files import (  # noqa: E402
    complete_chunked_upload,
    get_upload_temp_dir,
    upload_chunk,
    write_upload_metadata,
)
from app.routers import files as files_router  # noqa: E402
from app.schemas import ChunkedUploadCompleteRequest  # noqa: E402

TEST_TEMP_ROOT = os.path.join(os.path.dirname(__file__), "_tmp_upload_tests")
os.makedirs(TEST_TEMP_ROOT, exist_ok=True)


def make_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/api/files/upload",
            "headers": [(b"host", b"testserver")],
            "server": ("testserver", 80),
        }
    )


class ChunkUploadSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_invalid_upload_id_before_touching_disk(self):
        upload = UploadFile(filename="chunk.bin", file=io.BytesIO(b"abc"))
        user = SimpleNamespace(id="user-1", storage_quota=1024, storage_used=0)

        with self.assertRaises(HTTPException) as ctx:
            await upload_chunk(
                request=make_request(),
                upload_id="..",
                chunk_index=0,
                file=upload,
                current_user=user,
            )

        self.assertEqual(ctx.exception.status_code, 400)

    async def test_rejects_chunk_larger_than_declared_size(self):
        tempdir = os.path.join(TEST_TEMP_ROOT, f"storage-{uuid.uuid4()}")
        os.makedirs(tempdir, exist_ok=True)
        original_storage_path = files_router.settings.storage_path
        files_router.settings.storage_path = tempdir
        try:
            user = SimpleNamespace(id="user-1", storage_quota=1024, storage_used=0)
            upload_id = str(uuid.uuid4())
            session_dir = get_upload_temp_dir(user.id, upload_id)
            os.makedirs(session_dir, exist_ok=True)
            await write_upload_metadata(session_dir, total_size=5, chunk_size=2)

            upload = UploadFile(filename="chunk.bin", file=io.BytesIO(b"abc"))
            with self.assertRaises(HTTPException) as ctx:
                await upload_chunk(
                    request=make_request(),
                    upload_id=upload_id,
                    chunk_index=0,
                    file=upload,
                    current_user=user,
                )

            self.assertEqual(ctx.exception.status_code, 400)
            self.assertFalse(os.path.exists(os.path.join(session_dir, "chunk_0")))
        finally:
            files_router.settings.storage_path = original_storage_path
            shutil.rmtree(tempdir, ignore_errors=True)

    async def test_complete_rejects_missing_chunks(self):
        tempdir = os.path.join(TEST_TEMP_ROOT, f"storage-{uuid.uuid4()}")
        os.makedirs(tempdir, exist_ok=True)
        original_storage_path = files_router.settings.storage_path
        files_router.settings.storage_path = tempdir
        try:
            user = SimpleNamespace(id="user-1", storage_quota=1024, storage_used=0)
            upload_id = str(uuid.uuid4())
            session_dir = get_upload_temp_dir(user.id, upload_id)
            os.makedirs(session_dir, exist_ok=True)
            await write_upload_metadata(session_dir, total_size=3, chunk_size=2)

            with open(os.path.join(session_dir, "chunk_0"), "wb") as handle:
                handle.write(b"ab")

            request = ChunkedUploadCompleteRequest(
                upload_id=upload_id,
                filename="test.txt",
                total_size=3,
                path=[],
                mime_type="text/plain",
            )

            with self.assertRaises(HTTPException) as ctx:
                await complete_chunked_upload(
                    request=make_request(),
                    complete_req=request,
                    current_user=user,
                    db=object(),
                )

            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(ctx.exception.detail, "Upload is incomplete")
        finally:
            files_router.settings.storage_path = original_storage_path
            shutil.rmtree(tempdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
