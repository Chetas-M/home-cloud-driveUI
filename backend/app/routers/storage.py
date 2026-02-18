"""
Home Cloud Drive - Storage Router
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import User, File as FileModel, ActivityLog
from app.schemas import StorageResponse, StorageBreakdown, ActivityResponse
from app.auth import get_current_user
from app.config import get_settings

router = APIRouter(prefix="/api/storage", tags=["Storage"])


@router.get("", response_model=StorageResponse)
async def get_storage_info(
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
    
    # Get actual disk space from storage path
    storage_path = get_settings().storage_path
    try:
        disk_usage = shutil.disk_usage(storage_path)
        disk_total = disk_usage.total
        disk_free = disk_usage.free
    except:
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
async def get_activity_log(
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
async def empty_trash(
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
        # Delete from disk
        if file.storage_path and os.path.exists(file.storage_path):
            os.remove(file.storage_path)
        
        # Delete thumbnail from disk
        if file.thumbnail_path and os.path.exists(file.thumbnail_path):
            os.remove(file.thumbnail_path)
        
        total_freed += file.size
        await db.delete(file)
    
    # Update user storage
    current_user.storage_used -= total_freed
    if current_user.storage_used < 0:
        current_user.storage_used = 0
    
    await db.flush()
