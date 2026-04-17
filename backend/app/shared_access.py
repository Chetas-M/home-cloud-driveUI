"""
Helpers for shared-folder access control.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File as FileModel, SharedFolderAccess, User
from app.tree_validation import normalize_tree_path


ROLE_ORDER = {
    "viewer": 1,
    "editor": 2,
    "admin": 3,
    "owner": 4,
}


def parse_path(path_json: str | None) -> list[str]:
    try:
        return json.loads(path_json or "[]")
    except Exception:
        return []


def serialize_path(path: list[str]) -> str:
    return json.dumps(path, separators=(",", ":"))


def serialize_path_legacy(path: list[str]) -> str:
    return json.dumps(path)


def get_serialized_path_variants(path: list[str]) -> list[str]:
    return list({serialize_path(path), serialize_path_legacy(path)})


def resource_is_within_shared_root(resource: FileModel, shared_root: FileModel) -> bool:
    root_path = parse_path(shared_root.path)
    root_prefix = root_path + [shared_root.name]
    if resource.id == shared_root.id:
        return True
    resource_path = parse_path(resource.path)
    return resource.owner_id == shared_root.owner_id and resource_path[:len(root_prefix)] == root_prefix


def relative_path_within_shared_root(resource: FileModel, shared_root: FileModel) -> list[str]:
    if resource.id == shared_root.id:
        return []
    root_prefix = parse_path(shared_root.path) + [shared_root.name]
    resource_path = parse_path(resource.path)
    if resource_path[:len(root_prefix)] != root_prefix:
        raise HTTPException(status_code=403, detail="Access denied")
    return resource_path[len(root_prefix):]


def path_prefixes_for_shared_root(shared_root: FileModel) -> tuple[list[str], list[str]]:
    root_prefix = parse_path(shared_root.path) + [shared_root.name]
    return root_prefix, [f"{variant[:-1]}%" for variant in get_serialized_path_variants(root_prefix)]


def has_required_role(actual_role: str, required_role: str) -> bool:
    return ROLE_ORDER.get(actual_role, 0) >= ROLE_ORDER.get(required_role, 0)


@dataclass
class FileAccessContext:
    role: str
    is_owner: bool
    owner_id: str
    owner_username: Optional[str]
    shared_folder_id: Optional[str] = None
    shared_root: Optional[FileModel] = None

    @property
    def can_write(self) -> bool:
        return has_required_role(self.role, "editor")

    @property
    def can_manage(self) -> bool:
        return has_required_role(self.role, "admin")

    @property
    def can_share_public(self) -> bool:
        return self.is_owner


async def resolve_user_identifier(db: AsyncSession, identifier: str) -> Optional[User]:
    trimmed = identifier.strip()
    if not trimmed:
        return None

    if "@" in trimmed:
        result = await db.execute(select(User).where(User.email == trimmed))
        user = result.scalar_one_or_none()
        if user is not None:
            return user

    result = await db.execute(select(User).where(User.username == trimmed))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    if "@" not in trimmed:
        result = await db.execute(select(User).where(User.email == trimmed))
        return result.scalar_one_or_none()
    return None


async def get_shared_root_access(
    db: AsyncSession,
    current_user: User,
    shared_folder_id: str,
    *,
    required_role: str = "viewer",
    allow_trashed: bool = False,
) -> tuple[FileModel, FileAccessContext]:
    result = await db.execute(
        select(SharedFolderAccess, FileModel, User.username)
        .join(FileModel, SharedFolderAccess.folder_id == FileModel.id)
        .join(User, User.id == FileModel.owner_id)
        .where(
            and_(
                SharedFolderAccess.folder_id == shared_folder_id,
                SharedFolderAccess.user_id == current_user.id,
                FileModel.type == "folder",
            )
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Shared folder not found")

    access, folder, owner_username = row[0], row[1], row[2]
    if folder.is_trashed and not allow_trashed:
        raise HTTPException(status_code=404, detail="Shared folder not found")
    if not has_required_role(access.role, required_role):
        raise HTTPException(status_code=403, detail="Insufficient permissions for this shared folder")

    return folder, FileAccessContext(
        role=access.role,
        is_owner=False,
        owner_id=folder.owner_id,
        owner_username=owner_username,
        shared_folder_id=folder.id,
        shared_root=folder,
    )


async def get_file_access_context(
    db: AsyncSession,
    current_user: User,
    file_id: str,
    *,
    required_role: str = "viewer",
    allow_trashed: bool = False,
) -> tuple[FileModel, FileAccessContext]:
    result = await db.execute(
        select(FileModel, User.username)
        .join(User, User.id == FileModel.owner_id)
        .where(FileModel.id == file_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="File not found")

    file, owner_username = row[0], row[1]
    if file.is_trashed and not allow_trashed:
        raise HTTPException(status_code=404, detail="File not found")

    if file.owner_id == current_user.id:
        ctx = FileAccessContext(
            role="owner",
            is_owner=True,
            owner_id=file.owner_id,
            owner_username=owner_username,
        )
        if not has_required_role(ctx.role, required_role):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return file, ctx

    access_result = await db.execute(
        select(SharedFolderAccess, FileModel)
        .join(FileModel, SharedFolderAccess.folder_id == FileModel.id)
        .where(
            and_(
                SharedFolderAccess.user_id == current_user.id,
                SharedFolderAccess.owner_id == file.owner_id,
                FileModel.type == "folder",
            )
        )
    )

    matching_root = None
    matching_role = None
    for access, shared_root in access_result.all():
        if shared_root.is_trashed and not allow_trashed:
            continue
        if not resource_is_within_shared_root(file, shared_root):
            continue
        root_depth = len(parse_path(shared_root.path)) + 1
        if matching_root is None or root_depth > (len(parse_path(matching_root.path)) + 1):
            matching_root = shared_root
            matching_role = access.role

    if matching_root is None or matching_role is None:
        raise HTTPException(status_code=404, detail="File not found")
    if not has_required_role(matching_role, required_role):
        raise HTTPException(status_code=403, detail="Insufficient permissions for this shared folder")

    return file, FileAccessContext(
        role=matching_role,
        is_owner=False,
        owner_id=file.owner_id,
        owner_username=owner_username,
        shared_folder_id=matching_root.id,
        shared_root=matching_root,
    )


async def resolve_target_path(
    db: AsyncSession,
    current_user: User,
    raw_path: list[str] | None,
    *,
    shared_folder_id: Optional[str] = None,
    required_role: str = "viewer",
) -> tuple[list[str], FileAccessContext]:
    normalized_path = normalize_tree_path(raw_path)
    if not shared_folder_id:
        return normalized_path, FileAccessContext(
            role="owner",
            is_owner=True,
            owner_id=current_user.id,
            owner_username=current_user.username,
        )

    shared_root, ctx = await get_shared_root_access(
        db,
        current_user,
        shared_folder_id,
        required_role=required_role,
    )
    root_prefix = parse_path(shared_root.path) + [shared_root.name]
    return root_prefix + normalized_path, ctx
