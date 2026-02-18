"""
Home Cloud Drive - Folders Router
"""
import json
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models import User, File as FileModel, ActivityLog
from app.schemas import FolderCreate, FileResponse as FileResponseSchema
from app.auth import get_current_user

router = APIRouter(prefix="/api/folders", tags=["Folders"])


def parse_path(path_json: str) -> List[str]:
    try:
        return json.loads(path_json)
    except:
        return []


def serialize_path(path: List[str]) -> str:
    return json.dumps(path)


@router.post("", response_model=FileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_folder(
    folder: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new folder"""
    # Check if folder with same name exists in same path
    existing = await db.execute(
        select(FileModel).where(
            and_(
                FileModel.owner_id == current_user.id,
                FileModel.name == folder.name,
                FileModel.path == serialize_path(folder.path),
                FileModel.type == "folder",
                FileModel.is_trashed == False,
            )
        )
    )
    
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A folder with this name already exists in this location"
        )
    
    new_folder = FileModel(
        name=folder.name,
        type="folder",
        size=0,
        path=serialize_path(folder.path),
        owner_id=current_user.id,
    )
    
    db.add(new_folder)
    
    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="create_folder",
        file_name=folder.name,
    )
    db.add(activity)
    
    await db.flush()
    await db.refresh(new_folder)
    
    return FileResponseSchema(
        id=new_folder.id,
        name=new_folder.name,
        type=new_folder.type,
        mime_type=new_folder.mime_type,
        size=new_folder.size,
        path=parse_path(new_folder.path),
        is_starred=new_folder.is_starred,
        is_trashed=new_folder.is_trashed,
        created_at=new_folder.created_at,
        updated_at=new_folder.updated_at,
    )


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a folder and all its contents (move to trash)"""
    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == folder_id, FileModel.owner_id == current_user.id)
        )
    )
    folder = result.scalar_one_or_none()
    
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    
    if folder.type != "folder":
        raise HTTPException(status_code=400, detail="Not a folder")
    
    # Get folder path for finding children
    folder_path = parse_path(folder.path)
    folder_full_path = folder_path + [folder.name]
    folder_full_path_json = serialize_path(folder_full_path)
    
    # Get all files/folders inside this folder (and subfolders)
    children_result = await db.execute(
        select(FileModel).where(
            and_(
                FileModel.owner_id == current_user.id,
                FileModel.path.like(f'{folder_full_path_json[:-1]}%'),
            )
        )
    )
    children = children_result.scalars().all()
    
    # Trash all children
    for child in children:
        child.is_trashed = True
        child.trashed_at = datetime.now(timezone.utc)
    
    # Trash the folder itself
    folder.is_trashed = True
    folder.trashed_at = datetime.now(timezone.utc)
    
    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="trash",
        file_name=folder.name,
    )
    db.add(activity)
    
    await db.flush()
