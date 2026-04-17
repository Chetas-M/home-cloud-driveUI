"""
Shared folder management routes.
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.auth import get_current_user
from app.database import get_db
from app.models import ActivityLog, File as FileModel, SharedFolderAccess, User
from app.schemas import (
    FileResponse,
    SharedFolderAccessResponse,
    SharedFolderAccessUpdate,
    SharedFolderInviteCreate,
)
from app.shared_access import (
    get_file_access_context,
    relative_path_within_shared_root,
    resolve_user_identifier,
)

router = APIRouter(prefix="/api/shared-folders", tags=["Shared Folders"])


def build_folder_response(folder: FileModel, *, current_user: User, owner_username: str, role: str) -> FileResponse:
    is_owner = folder.owner_id == current_user.id
    return FileResponse(
        id=folder.id,
        name=folder.name,
        type=folder.type,
        mime_type=folder.mime_type,
        size=folder.size,
        path=[],
        is_starred=folder.is_starred,
        is_trashed=folder.is_trashed,
        thumbnail_url=None,
        version=folder.version or 1,
        is_shared=not is_owner,
        is_shared_root=not is_owner,
        shared_folder_id=folder.id if not is_owner else None,
        access_role="owner" if is_owner else role,
        owner_id=folder.owner_id,
        owner_username=owner_username,
        can_write=is_owner or role in {"editor", "admin"},
        can_manage=is_owner or role == "admin",
        can_share_public=is_owner,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


def build_access_response(access: SharedFolderAccess, user: User, invited_by: str | None) -> SharedFolderAccessResponse:
    return SharedFolderAccessResponse(
        id=access.id,
        folder_id=access.folder_id,
        role=access.role,
        created_at=access.created_at,
        updated_at=access.updated_at,
        user_id=user.id,
        username=user.username,
        email=user.email,
        invited_by=invited_by,
    )


async def assert_folder_admin_access(
    db: AsyncSession,
    current_user: User,
    folder_id: str,
) -> tuple[FileModel, bool]:
    folder, ctx = await get_file_access_context(db, current_user, folder_id, required_role="admin")
    if folder.type != "folder":
        raise HTTPException(status_code=400, detail="Shared access can only be managed for folders")
    if not ctx.is_owner and ctx.shared_folder_id != folder.id:
        raise HTTPException(status_code=403, detail="You can only manage access on the shared folder root")
    return folder, ctx.is_owner


@router.get("", response_model=List[FileResponse])
async def list_shared_folders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SharedFolderAccess, FileModel, User.username)
        .join(FileModel, SharedFolderAccess.folder_id == FileModel.id)
        .join(User, User.id == FileModel.owner_id)
        .where(
            and_(
                SharedFolderAccess.user_id == current_user.id,
                FileModel.type == "folder",
                FileModel.is_trashed == False,
            )
        )
        .order_by(FileModel.updated_at.desc(), FileModel.name.asc())
    )
    return [
        build_folder_response(folder, current_user=current_user, owner_username=owner_username, role=access.role)
        for access, folder, owner_username in result.all()
    ]


@router.get("/{folder_id}/access", response_model=List[SharedFolderAccessResponse])
async def list_folder_access(
    folder_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await assert_folder_admin_access(db, current_user, folder_id)
    inviter = aliased(User)
    result = await db.execute(
        select(SharedFolderAccess, User, inviter.username)
        .join(User, User.id == SharedFolderAccess.user_id)
        .outerjoin(inviter, inviter.id == SharedFolderAccess.invited_by)
        .where(SharedFolderAccess.folder_id == folder_id)
        .order_by(User.username.asc())
    )
    return [
        build_access_response(access, invited_user, invited_by_username)
        for access, invited_user, invited_by_username in result.all()
    ]


@router.post("/{folder_id}/access", response_model=SharedFolderAccessResponse, status_code=status.HTTP_201_CREATED)
async def invite_to_shared_folder(
    folder_id: str,
    payload: SharedFolderInviteCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder, is_owner = await assert_folder_admin_access(db, current_user, folder_id)
    target_user = await resolve_user_identifier(db, payload.identifier)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    if target_user.id == folder.owner_id:
        raise HTTPException(status_code=400, detail="The folder owner already has full access")

    existing_result = await db.execute(
        select(SharedFolderAccess).where(
            and_(
                SharedFolderAccess.folder_id == folder_id,
                SharedFolderAccess.user_id == target_user.id,
            )
        )
    )
    existing = existing_result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.role = payload.role
        existing.invited_by = current_user.id
        existing.updated_at = now
        access = existing
    else:
        access = SharedFolderAccess(
            folder_id=folder_id,
            owner_id=folder.owner_id,
            user_id=target_user.id,
            role=payload.role,
            invited_by=current_user.id,
            created_at=now,
            updated_at=now,
        )
        db.add(access)

    db.add(ActivityLog(
        user_id=current_user.id,
        action="share_folder" if is_owner else "share_folder_admin",
        file_name=f"{folder.name} -> {target_user.username} ({payload.role})",
    ))
    await db.flush()
    await db.refresh(access)
    return build_access_response(access, target_user, current_user.username)


@router.patch("/{folder_id}/access/{access_id}", response_model=SharedFolderAccessResponse)
async def update_shared_folder_access(
    folder_id: str,
    access_id: str,
    payload: SharedFolderAccessUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder, _is_owner = await assert_folder_admin_access(db, current_user, folder_id)
    result = await db.execute(
        select(SharedFolderAccess, User)
        .join(User, User.id == SharedFolderAccess.user_id)
        .where(
            and_(
                SharedFolderAccess.id == access_id,
                SharedFolderAccess.folder_id == folder_id,
            )
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Shared access entry not found")

    access, invited_user = row[0], row[1]
    access.role = payload.role
    access.invited_by = current_user.id
    access.updated_at = datetime.now(timezone.utc)
    db.add(ActivityLog(
        user_id=current_user.id,
        action="share_folder_role_update",
        file_name=f"{folder.name} -> {invited_user.username} ({payload.role})",
    ))
    await db.flush()
    return build_access_response(access, invited_user, current_user.username)


@router.delete("/{folder_id}/access/{access_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_shared_folder_access(
    folder_id: str,
    access_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    folder, _is_owner = await assert_folder_admin_access(db, current_user, folder_id)
    result = await db.execute(
        select(SharedFolderAccess, User)
        .join(User, User.id == SharedFolderAccess.user_id)
        .where(
            and_(
                SharedFolderAccess.id == access_id,
                SharedFolderAccess.folder_id == folder_id,
            )
        )
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Shared access entry not found")

    access, invited_user = row[0], row[1]
    db.add(ActivityLog(
        user_id=current_user.id,
        action="share_folder_removed",
        file_name=f"{folder.name} -> {invited_user.username}",
    ))
    await db.delete(access)
    await db.flush()
