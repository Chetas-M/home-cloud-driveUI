"""
Validation helpers for folder/file tree metadata.
"""
import unicodedata
from typing import List

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_


def sanitize_tree_name(name: str | None) -> str:
    """Validate a single folder/file path segment without rewriting it."""
    if name is None or name == "":
        raise HTTPException(status_code=400, detail="File/folder name is invalid")

    if name != name.strip() or name != name.strip("."):
        raise HTTPException(status_code=400, detail="File/folder name is invalid")

    for char in name:
        if char in {"/", "\\", "\r", "\n", "\x00"}:
            raise HTTPException(status_code=400, detail="File/folder name is invalid")
        if unicodedata.category(char).startswith("C"):
            raise HTTPException(status_code=400, detail="File/folder name is invalid")

    return name


def normalize_tree_path(path: List[str] | None) -> List[str]:
    """Validate a JSON path array from the client without changing segments."""
    if path is None:
        return []
    if not isinstance(path, list):
        raise HTTPException(status_code=400, detail="Path is invalid")
    return [sanitize_tree_name(segment) for segment in path]


async def ensure_folder_path_exists(
    db: AsyncSession,
    user_id: str,
    path: List[str],
    *,
    error_detail: str = "Parent folder does not exist",
) -> None:
    """Check that every segment of *path* resolves to a real, non-trashed folder
    belonging to *user_id*.  Raises HTTP 400 when the folder cannot be found."""
    if not path:
        return

    # Import here to avoid a top-level circular-import with models → database.
    from app.models import File as FileModel  # noqa: PLC0415

    def _serialize(p: List[str]) -> str:
        import json
        return json.dumps(p, separators=(",", ":"))

    def _serialize_legacy(p: List[str]) -> str:
        import json
        return json.dumps(p)

    def _path_variants(p: List[str]) -> List[str]:
        return list({_serialize(p), _serialize_legacy(p)})

    parent_path = path[:-1]
    folder_name = path[-1]
    result = await db.execute(
        select(FileModel.id).where(
            and_(
                FileModel.owner_id == user_id,
                FileModel.type == "folder",
                FileModel.name == folder_name,
                FileModel.path.in_(_path_variants(parent_path)),
                FileModel.is_trashed == False,  # noqa: E712
            )
        )
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=400, detail=error_detail)
