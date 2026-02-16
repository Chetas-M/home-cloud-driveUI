"""
Home Cloud Drive - Files Router
"""
import os
import json
import uuid
import aiofiles
import mimetypes
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models import User, File as FileModel, ActivityLog
from app.schemas import FileResponse as FileResponseSchema, FileUpdate, FileMoveRequest
from app.auth import get_current_user
from app.config import get_settings
from app.thumbnails import generate_thumbnail, can_generate_thumbnail

settings = get_settings()
router = APIRouter(prefix="/api/files", tags=["Files"])


def get_file_type(filename: str, mime_type: str = None) -> str:
    """Determine file type from filename and mime type"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    
    image_exts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg', 'bmp', 'ico']
    video_exts = ['mp4', 'webm', 'avi', 'mov', 'mkv', 'flv', 'wmv']
    pdf_exts = ['pdf']
    text_exts = ['txt', 'md', 'json', 'xml', 'html', 'css', 'js', 'py', 'java', 'cpp', 'c']
    archive_exts = ['zip', 'rar', '7z', 'tar', 'gz', 'bz2']
    
    if ext in image_exts:
        return 'image'
    elif ext in video_exts:
        return 'video'
    elif ext in pdf_exts:
        return 'pdf'
    elif ext in text_exts:
        return 'text'
    elif ext in archive_exts:
        return 'archive'
    else:
        return 'file'


def parse_path(path_json: str) -> List[str]:
    """Parse stored path JSON to list"""
    try:
        return json.loads(path_json)
    except:
        return []


def serialize_path(path: List[str]) -> str:
    """Serialize path list to JSON"""
    return json.dumps(path)


@router.get("", response_model=List[FileResponseSchema])
async def list_files(
    path: Optional[str] = Query(None, description="Path as JSON array"),
    include_trashed: bool = Query(False),
    starred_only: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List files in a directory"""
    query = select(FileModel).where(FileModel.owner_id == current_user.id)
    
    if not include_trashed:
        query = query.where(FileModel.is_trashed == False)
    
    if starred_only:
        query = query.where(FileModel.is_starred == True)
    
    if path:
        query = query.where(FileModel.path == path)
    
    result = await db.execute(query.order_by(FileModel.type, FileModel.name))
    files = result.scalars().all()
    
    # Convert to response format
    response = []
    for f in files:
        thumb_url = f"/api/files/{f.id}/thumbnail" if f.thumbnail_path else None
        response.append(FileResponseSchema(
            id=f.id,
            name=f.name,
            type=f.type,
            mime_type=f.mime_type,
            size=f.size,
            path=parse_path(f.path),
            is_starred=f.is_starred,
            is_trashed=f.is_trashed,
            thumbnail_url=thumb_url,
            created_at=f.created_at,
            updated_at=f.updated_at,
        ))
    
    return response


@router.post("/upload", response_model=List[FileResponseSchema], status_code=status.HTTP_201_CREATED)
async def upload_files(
    files: List[UploadFile] = File(...),
    path: Optional[str] = Query("[]", description="Path as JSON array"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload one or more files"""
    # Check storage quota
    total_size = 0
    for file in files:
        content = await file.read()
        total_size += len(content)
        await file.seek(0)  # Reset file position
    
    if current_user.storage_quota > 0 and current_user.storage_used + total_size > current_user.storage_quota:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Storage quota exceeded. Available: {current_user.storage_quota - current_user.storage_used} bytes"
        )
    
    # Ensure storage directory exists
    user_storage_path = os.path.join(settings.storage_path, current_user.id)
    os.makedirs(user_storage_path, exist_ok=True)
    
    uploaded_files = []
    
    for file in files:
        # Generate unique filename
        file_id = str(uuid.uuid4())
        ext = file.filename.split('.')[-1] if '.' in file.filename else ''
        storage_filename = f"{file_id}.{ext}" if ext else file_id
        storage_filepath = os.path.join(user_storage_path, storage_filename)
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Save file
        async with aiofiles.open(storage_filepath, 'wb') as f:
            await f.write(content)
        
        # Get mime type
        mime_type = file.content_type or mimetypes.guess_type(file.filename)[0]
        
        # Generate thumbnail for images
        thumb_path = None
        if can_generate_thumbnail(file.filename):
            thumb_dir = os.path.join(user_storage_path, "thumbnails")
            thumb_path = generate_thumbnail(storage_filepath, thumb_dir, file_id)
        
        # Create database entry with explicit defaults
        now = datetime.utcnow()
        new_file = FileModel(
            id=file_id,
            name=file.filename,
            type=get_file_type(file.filename, mime_type),
            mime_type=mime_type,
            size=file_size,
            path=path,
            storage_path=storage_filepath,
            thumbnail_path=thumb_path,
            owner_id=current_user.id,
            is_starred=False,
            is_trashed=False,
            created_at=now,
            updated_at=now,
        )
        
        db.add(new_file)
        
        # Update user storage
        current_user.storage_used += file_size
        
        # Log activity
        activity = ActivityLog(
            user_id=current_user.id,
            action="upload",
            file_name=file.filename,
        )
        db.add(activity)
        
        thumb_url = f"/api/files/{new_file.id}/thumbnail" if new_file.thumbnail_path else None
        uploaded_files.append(FileResponseSchema(
            id=new_file.id,
            name=new_file.name,
            type=new_file.type,
            mime_type=new_file.mime_type,
            size=new_file.size,
            path=parse_path(new_file.path),
            is_starred=new_file.is_starred,
            is_trashed=new_file.is_trashed,
            thumbnail_url=thumb_url,
            created_at=new_file.created_at,
            updated_at=new_file.updated_at,
        ))
    
    await db.flush()
    return uploaded_files


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Download a file"""
    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.owner_id == current_user.id)
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if file.type == "folder":
        raise HTTPException(status_code=400, detail="Cannot download a folder")
    
    if not file.storage_path or not os.path.exists(file.storage_path):
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="download",
        file_name=file.name,
    )
    db.add(activity)
    await db.flush()
    
    return FileResponse(
        path=file.storage_path,
        filename=file.name,
        media_type=file.mime_type or "application/octet-stream"
    )


@router.patch("/{file_id}", response_model=FileResponseSchema)
async def update_file(
    file_id: str,
    update: FileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update file (rename, move, star)"""
    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.owner_id == current_user.id)
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    if update.name is not None:
        old_name = file.name
        file.name = update.name
        activity = ActivityLog(
            user_id=current_user.id,
            action="rename",
            file_name=f"{old_name} → {update.name}",
        )
        db.add(activity)
    
    if update.path is not None:
        file.path = serialize_path(update.path)
        activity = ActivityLog(
            user_id=current_user.id,
            action="move",
            file_name=file.name,
        )
        db.add(activity)
    
    if update.is_starred is not None:
        file.is_starred = update.is_starred
        if update.is_starred:
            activity = ActivityLog(
                user_id=current_user.id,
                action="star",
                file_name=file.name,
            )
            db.add(activity)
    
    file.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(file)
    
    return FileResponseSchema(
        id=file.id,
        name=file.name,
        type=file.type,
        mime_type=file.mime_type,
        size=file.size,
        path=parse_path(file.path),
        is_starred=file.is_starred,
        is_trashed=file.is_trashed,
        created_at=file.created_at,
        updated_at=file.updated_at,
    )


@router.post("/{file_id}/trash", response_model=FileResponseSchema)
async def trash_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Move file to trash"""
    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.owner_id == current_user.id)
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    file.is_trashed = True
    file.trashed_at = datetime.utcnow()
    file.updated_at = datetime.utcnow()
    
    activity = ActivityLog(
        user_id=current_user.id,
        action="trash",
        file_name=file.name,
    )
    db.add(activity)
    
    await db.flush()
    await db.refresh(file)
    
    return FileResponseSchema(
        id=file.id,
        name=file.name,
        type=file.type,
        mime_type=file.mime_type,
        size=file.size,
        path=parse_path(file.path),
        is_starred=file.is_starred,
        is_trashed=file.is_trashed,
        created_at=file.created_at,
        updated_at=file.updated_at,
    )


@router.post("/{file_id}/restore", response_model=FileResponseSchema)
async def restore_file(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Restore file from trash"""
    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.owner_id == current_user.id)
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    file.is_trashed = False
    file.trashed_at = None
    file.updated_at = datetime.utcnow()
    
    activity = ActivityLog(
        user_id=current_user.id,
        action="restore",
        file_name=file.name,
    )
    db.add(activity)
    
    await db.flush()
    await db.refresh(file)
    
    return FileResponseSchema(
        id=file.id,
        name=file.name,
        type=file.type,
        mime_type=file.mime_type,
        size=file.size,
        path=parse_path(file.path),
        is_starred=file.is_starred,
        is_trashed=file.is_trashed,
        created_at=file.created_at,
        updated_at=file.updated_at,
    )


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file_permanently(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Permanently delete a file"""
    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.owner_id == current_user.id)
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete file from disk
    if file.storage_path and os.path.exists(file.storage_path):
        os.remove(file.storage_path)
    
    # Delete thumbnail if exists
    if file.thumbnail_path and os.path.exists(file.thumbnail_path):
        os.remove(file.thumbnail_path)
    
    # Update user storage
    current_user.storage_used -= file.size
    if current_user.storage_used < 0:
        current_user.storage_used = 0
    
    # Delete from database
    await db.delete(file)
    await db.flush()


@router.get("/{file_id}/thumbnail")
async def get_thumbnail(
    file_id: str,
    token: str = Query(None, description="Auth token for img src usage"),
    current_user: User = None,
    db: AsyncSession = Depends(get_db)
):
    """Serve a file's thumbnail image. Accepts token via query param for img src."""
    from app.config import get_settings
    from jose import jwt, JWTError
    
    _settings = get_settings()
    
    # Try to get user from query token
    if token and not current_user:
        try:
            payload = jwt.decode(token, _settings.secret_key, algorithms=[_settings.algorithm])
            user_id = payload.get("sub")
            if user_id:
                result = await db.execute(select(User).where(User.id == user_id))
                current_user = result.scalar_one_or_none()
        except JWTError:
            pass
    
    if not current_user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.owner_id == current_user.id)
        )
    )
    file = result.scalar_one_or_none()
    
    if not file or not file.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    
    if not os.path.exists(file.thumbnail_path):
        raise HTTPException(status_code=404, detail="Thumbnail file missing")
    
    return FileResponse(
        path=file.thumbnail_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"}
    )
