"""
Home Cloud Drive - Storage Router
"""
from typing import List
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.limiter import limiter
from app.models import User, File as FileModel, ActivityLog, FileVersion
from app.schemas import StorageResponse, StorageBreakdown, ActivityResponse
from app.auth import get_current_user
from app.config import get_settings

router = APIRouter(prefix="/api/storage", tags=["Storage"])


@router.get("", response_model=StorageResponse)
@limiter.limit("60/minute")
async def get_storage_info(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get storage usage statistics"""
    import shutil
    
    # Get breakdown by file type
    result = await db.execute(
        select(
            FileModel.type,
            func.sum(FileModel.size).label('total_size'),
            func.count(FileModel.id).label('count')
        )
        .where(FileModel.owner_id == current_user.id)
        .where(FileModel.is_trashed == False)
        .where(FileModel.type != 'folder')
        .group_by(FileModel.type)
    )
    
    breakdown = []
    for row in result:
        breakdown.append(StorageBreakdown(
            type=row[0],
            size=row[1] or 0,
            count=row[2] or 0,
        ))

    # Add archived version storage so totals reflect historical copies
    version_stats = await db.execute(
        select(
            func.sum(FileVersion.size),
            func.count(FileVersion.id)
        )
        .join(FileModel, FileVersion.file_id == FileModel.id)
        .where(FileModel.owner_id == current_user.id)
        .where(FileVersion.version != FileModel.version)
    )
    version_sum, version_count = version_stats.first() or (0, 0)
    if version_sum:
        breakdown.append(StorageBreakdown(
            type="versions",
            size=version_sum or 0,
            count=version_count or 0,
        ))
    
    # Get actual disk space from storage path
    storage_path = get_settings().storage_path
    try:
        disk_usage = shutil.disk_usage(storage_path)
        disk_total = disk_usage.total
        disk_free = disk_usage.free
    except Exception:
        disk_total = 0
        disk_free = 0
    
    # Use user quota if set, otherwise use disk total
    effective_quota = current_user.storage_quota if current_user.storage_quota > 0 else disk_total
    percent_used = (current_user.storage_used / effective_quota * 100) if effective_quota > 0 else 0
    
    return StorageResponse(
        used=current_user.storage_used,
        quota=effective_quota,
        percent_used=round(percent_used, 2),
        breakdown=breakdown,
        disk_total=disk_total,
        disk_free=disk_free,
    )


@router.get("/activity", response_model=List[ActivityResponse])
@limiter.limit("60/minute")
async def get_activity_log(
    request: Request,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get recent activity log"""
    result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.user_id == current_user.id)
        .order_by(ActivityLog.timestamp.desc())
        .limit(limit)
    )
    
    activities = result.scalars().all()
    return [ActivityResponse(
        action=a.action,
        file_name=a.file_name,
        timestamp=a.timestamp,
    ) for a in activities]


@router.delete("/trash", status_code=204)
@limiter.limit("10/minute")
async def empty_trash(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Empty trash - permanently delete all trashed files"""
    import os
    
    result = await db.execute(
        select(FileModel)
        .where(FileModel.owner_id == current_user.id)
        .where(FileModel.is_trashed == True)
    )
    
    trashed_files = result.scalars().all()
    total_freed = 0
    
    for file in trashed_files:
        versions_result = await db.execute(
            select(FileVersion).where(FileVersion.file_id == file.id)
        )
        versions = versions_result.scalars().all()

        if versions:
            for version in versions:
                if version.storage_path and os.path.exists(version.storage_path):
                    try:
                        os.remove(version.storage_path)
                    except OSError:
                        pass
                total_freed += version.size or 0
                await db.delete(version)
        else:
            if file.storage_path and os.path.exists(file.storage_path):
                try:
                    os.remove(file.storage_path)
                except OSError:
                    pass
            total_freed += file.size or 0
        
        # Delete thumbnail from disk
        if file.thumbnail_path and os.path.exists(file.thumbnail_path):
            try:
                os.remove(file.thumbnail_path)
            except OSError:
                pass
        
        await db.delete(file)
    
    # Update user storage
    current_user.storage_used -= total_freed
    if current_user.storage_used < 0:
        current_user.storage_used = 0
    
    await db.flush()
