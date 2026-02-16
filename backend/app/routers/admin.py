"""
Home Cloud Drive - Admin Router
Provides admin-only endpoints for user and system management.
"""
import os
import shutil
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.database import get_db
from app.models import User, File as FileModel, ActivityLog
from app.schemas import AdminUserResponse, AdminUserUpdate, SystemStats
from app.auth import get_admin_user, get_password_hash
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/users", response_model=List[AdminUserResponse])
async def list_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """List all users with file counts"""
    result = await db.execute(
        select(
            User,
            func.count(FileModel.id).label("file_count")
        )
        .outerjoin(FileModel, (FileModel.owner_id == User.id) & (FileModel.is_trashed == False))
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )

    users = []
    for row in result:
        user = row[0]
        file_count = row[1] or 0
        users.append(AdminUserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            is_admin=user.is_admin,
            storage_used=user.storage_used,
            storage_quota=user.storage_quota,
            file_count=file_count,
            created_at=user.created_at,
        ))
    return users


@router.get("/users/{user_id}", response_model=AdminUserResponse)
async def get_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a single user's details"""
    result = await db.execute(
        select(
            User,
            func.count(FileModel.id).label("file_count")
        )
        .outerjoin(FileModel, (FileModel.owner_id == User.id) & (FileModel.is_trashed == False))
        .where(User.id == user_id)
        .group_by(User.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    user = row[0]
    return AdminUserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        is_admin=user.is_admin,
        storage_used=user.storage_used,
        storage_quota=user.storage_quota,
        file_count=row[1] or 0,
        created_at=user.created_at,
    )


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: str,
    update: AdminUserUpdate,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Update user quota, admin status, etc."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent removing own admin status
    if update.is_admin is not None and user.id == admin.id and not update.is_admin:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove your own admin status"
        )

    if update.storage_quota is not None:
        user.storage_quota = update.storage_quota
    if update.is_admin is not None:
        user.is_admin = update.is_admin
    if update.username is not None:
        user.username = update.username
    if update.email is not None:
        user.email = update.email

    await db.flush()
    await db.refresh(user)

    # Get file count
    count_result = await db.execute(
        select(func.count(FileModel.id))
        .where(FileModel.owner_id == user.id)
        .where(FileModel.is_trashed == False)
    )
    file_count = count_result.scalar() or 0

    return AdminUserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        is_admin=user.is_admin,
        storage_used=user.storage_used,
        storage_quota=user.storage_quota,
        file_count=file_count,
        created_at=user.created_at,
    )


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a user and all their files"""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Delete user's files from disk
    user_storage_path = os.path.join(settings.storage_path, user.id)
    if os.path.exists(user_storage_path):
        shutil.rmtree(user_storage_path, ignore_errors=True)

    # Delete user's activity logs
    await db.execute(
        delete(ActivityLog).where(ActivityLog.user_id == user_id)
    )

    # Delete user (cascades to files via relationship)
    await db.delete(user)
    await db.flush()


@router.get("/stats", response_model=SystemStats)
async def get_system_stats(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db)
):
    """Get system-wide statistics"""
    # Total users
    user_count = await db.execute(select(func.count(User.id)))
    total_users = user_count.scalar() or 0

    # Total files (non-folder, non-trashed)
    file_count = await db.execute(
        select(func.count(FileModel.id))
        .where(FileModel.type != "folder")
        .where(FileModel.is_trashed == False)
    )
    total_files = file_count.scalar() or 0

    # Total storage
    storage_result = await db.execute(
        select(
            func.sum(User.storage_used),
            func.sum(User.storage_quota)
        )
    )
    row = storage_result.first()
    total_used = row[0] or 0
    total_quota = row[1] or 0

    # Disk info
    try:
        disk = shutil.disk_usage(settings.storage_path)
        disk_total = disk.total
        disk_free = disk.free
    except Exception:
        disk_total = 0
        disk_free = 0

    return SystemStats(
        total_users=total_users,
        total_files=total_files,
        total_storage_used=total_used,
        total_storage_quota=total_quota,
        disk_total=disk_total,
        disk_free=disk_free,
    )
