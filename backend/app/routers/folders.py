"""
Home Cloud Drive - Folders Router
"""
import json
from typing import List
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update as sql_update

from app.database import get_db
from app.models import User, File as FileModel, ActivityLog, ShareLink
from app.schemas import FolderCreate, FileResponse as FileResponseSchema
from app.auth import get_current_user
from app.shared_access import get_file_access_context, relative_path_within_shared_root, resolve_target_path
from app.tree_validation import sanitize_tree_name, ensure_folder_path_exists

router = APIRouter(prefix="/api/folders", tags=["Folders"])


def parse_path(path_json: str) -> List[str]:
    try:
        return json.loads(path_json)
    except Exception:
        return []


def serialize_path(path: List[str]) -> str:
    return json.dumps(path, separators=(",", ":"))


def serialize_path_legacy(path: List[str]) -> str:
    """Legacy JSON serialization used by older DB rows."""
    return json.dumps(path)


def get_serialized_path_variants(path: List[str]) -> List[str]:
    """Return all known serialized forms for the same logical path."""
    return list({serialize_path(path), serialize_path_legacy(path)})


def get_serialized_path_prefixes(path: List[str]) -> List[str]:
    """Return LIKE prefixes for all known serialized path forms."""
    return [f"{variant[:-1]}%" for variant in get_serialized_path_variants(path)]


@router.post("", response_model=FileResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_folder(
    folder: FolderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new folder"""
    normalized_name = sanitize_tree_name(folder.name)
    normalized_path, access_ctx = await resolve_target_path(
        db,
        current_user,
        folder.path,
        shared_folder_id=folder.shared_folder_id,
        required_role="editor",
    )
    owner_id = access_ctx.owner_id
    await ensure_folder_path_exists(db, owner_id, normalized_path)

    # Check if folder with same name exists in same path
    existing = await db.execute(
        select(FileModel).where(
            and_(
                FileModel.owner_id == owner_id,
                FileModel.name == normalized_name,
                FileModel.path.in_(get_serialized_path_variants(normalized_path)),
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
        name=normalized_name,
        type="folder",
        size=0,
        path=serialize_path(normalized_path),
        owner_id=owner_id,
        version=1,
    )
    
    db.add(new_folder)
    
    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="create_folder",
        file_name=normalized_name,
    )
    db.add(activity)
    
    await db.flush()
    await db.refresh(new_folder)
    
    path_override = (
        relative_path_within_shared_root(new_folder, access_ctx.shared_root)
        if access_ctx.shared_root is not None
        else None
    )
    return FileResponseSchema(
        id=new_folder.id,
        name=new_folder.name,
        type=new_folder.type,
        mime_type=new_folder.mime_type,
        size=new_folder.size,
        path=path_override if path_override is not None else parse_path(new_folder.path),
        is_starred=new_folder.is_starred,
        is_trashed=new_folder.is_trashed,
        version=new_folder.version or 1,
        is_shared=not access_ctx.is_owner,
        is_shared_root=False,
        shared_folder_id=access_ctx.shared_folder_id,
        access_role=access_ctx.role,
        owner_id=new_folder.owner_id,
        owner_username=access_ctx.owner_username,
        can_write=access_ctx.can_write,
        can_manage=access_ctx.can_manage,
        can_share_public=access_ctx.can_share_public,
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
    folder, _access_ctx = await get_file_access_context(db, current_user, folder_id, required_role="admin")
    
    if folder.type != "folder":
        raise HTTPException(status_code=400, detail="Not a folder")
    
    # Get folder path for finding children
    folder_path = parse_path(folder.path)
    folder_full_path = folder_path + [folder.name]
    folder_path_prefixes = get_serialized_path_prefixes(folder_full_path)
    
    # Get all files/folders inside this folder (and subfolders)
    children_result = await db.execute(
        select(FileModel).where(
            and_(
                FileModel.owner_id == folder.owner_id,
                or_(*[FileModel.path.like(prefix) for prefix in folder_path_prefixes]),
            )
        )
    )
    children = children_result.scalars().all()
    affected_ids = [folder.id]
    
    # Trash all children
    for child in children:
        child.is_trashed = True
        child.trashed_at = datetime.now(timezone.utc)
        affected_ids.append(child.id)
    
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

    await db.execute(
        sql_update(ShareLink)
        .where(
            ShareLink.file_id.in_(affected_ids),
            ShareLink.is_active == True,
        )
        .values(is_active=False)
    )

    await db.flush()
