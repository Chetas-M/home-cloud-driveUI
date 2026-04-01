"""
Home Cloud Drive - Files Router
"""
import os
import json
import uuid
import asyncio
import aiofiles
import mimetypes
import unicodedata
from urllib.parse import quote
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import logging

from app.database import get_db
from app.limiter import limiter
from app.models import User, File as FileModel, ActivityLog
from app.schemas import FileResponse as FileResponseSchema, FileUpdate, FileMoveRequest, SearchResult
from app.schemas import (
    FileResponse as FileResponseSchema, 
    FileUpdate, 
    FileMoveRequest,
    ChunkedUploadInitRequest,
    ChunkedUploadInitResponse,
    ChunkedUploadCompleteRequest
)
from app.auth import get_current_user
from app.config import get_settings
from app.db_utils import LIKE_ESCAPE_CHAR, escape_like_literal
from app.search_index import build_match_context, build_search_document
from app.thumbnails import generate_thumbnail, can_generate_thumbnail

settings = get_settings()
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/files", tags=["Files"])

CHUNK_SIZE = 1024 * 1024  # 1 MB chunks for streaming uploads
RESUMABLE_CHUNK_SIZE = 5 * 1024 * 1024
UPLOAD_METADATA_FILENAME = "upload.json"


def sanitize_filename(filename: Optional[str]) -> str:
    """Normalize uploaded filenames before storing or reflecting them."""
    if not filename:
        return "unnamed"

    sanitized_chars = []
    for char in filename.replace("\x00", ""):
        if char in {"/", "\\", "\r", "\n"}:
            sanitized_chars.append("_")
            continue

        # Remove control/format characters such as bidi overrides.
        if unicodedata.category(char).startswith("C"):
            continue

        sanitized_chars.append(char)

    sanitized = "".join(sanitized_chars).strip().strip(".")
    return sanitized or "unnamed"


def build_content_disposition(disposition: str, filename: str) -> str:
    """Create a safe Content-Disposition header value."""
    # Restrict disposition to a small allowlist to prevent header injection.
    allowed_dispositions = {"inline", "attachment"}
    normalized_disposition = (disposition or "").strip().lower()
    if normalized_disposition not in allowed_dispositions:
        normalized_disposition = "attachment"

    safe_name = sanitize_filename(filename)
    ascii_name = unicodedata.normalize("NFKD", safe_name).encode("ascii", "ignore").decode("ascii")
    ascii_name = "".join(
        char if char.isalnum() or char in {" ", ".", "_", "-"} else "_"
        for char in ascii_name
    ).strip() or "file"
    encoded_name = quote(safe_name, safe="")
    return f"{normalized_disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"


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
    except Exception:
        return []


def serialize_path(path: List[str]) -> str:
    """Serialize path list to JSON"""
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


def normalize_path(path_json: str) -> str:
    """Normalize incoming path JSON for stable DB comparisons."""
    return serialize_path(parse_path(path_json or "[]"))


def validate_upload_id(upload_id: str) -> str:
    """Only accept server-generated UUID upload ids."""
    try:
        return str(uuid.UUID(upload_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid upload session") from exc


def get_upload_temp_dir(user_id: str, upload_id: str) -> str:
    return os.path.join(settings.storage_path, "tmp", user_id, upload_id)


def get_upload_metadata_path(temp_dir: str) -> str:
    return os.path.join(temp_dir, UPLOAD_METADATA_FILENAME)


def get_expected_chunk_count(total_size: int, chunk_size: int) -> int:
    return max(1, (total_size + chunk_size - 1) // chunk_size)


def get_expected_chunk_size(total_size: int, chunk_size: int, chunk_index: int) -> int:
    expected_chunks = get_expected_chunk_count(total_size, chunk_size)
    if chunk_index < 0 or chunk_index >= expected_chunks:
        raise HTTPException(status_code=400, detail="Chunk index is out of range for this upload")
    if total_size == 0:
        return 0
    if chunk_index == expected_chunks - 1:
        return total_size - (chunk_index * chunk_size)
    return chunk_size


async def write_upload_metadata(temp_dir: str, total_size: int, chunk_size: int) -> None:
    metadata = {
        "total_size": total_size,
        "chunk_size": chunk_size,
        "expected_chunks": get_expected_chunk_count(total_size, chunk_size),
    }
    async with aiofiles.open(get_upload_metadata_path(temp_dir), "w", encoding="utf-8") as handle:
        await handle.write(json.dumps(metadata, separators=(",", ":")))


async def read_upload_metadata(temp_dir: str) -> dict:
    metadata_path = get_upload_metadata_path(temp_dir)
    if not os.path.exists(metadata_path):
        raise HTTPException(status_code=404, detail="Upload session not found or expired")

    try:
        async with aiofiles.open(metadata_path, "r", encoding="utf-8") as handle:
            metadata = json.loads(await handle.read())
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="Upload session metadata is invalid") from exc

    try:
        total_size = int(metadata["total_size"])
        chunk_size = int(metadata["chunk_size"])
        expected_chunks = int(metadata["expected_chunks"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Upload session metadata is invalid") from exc

    if total_size < 0 or chunk_size <= 0 or expected_chunks != get_expected_chunk_count(total_size, chunk_size):
        raise HTTPException(status_code=400, detail="Upload session metadata is invalid")

    return {
        "total_size": total_size,
        "chunk_size": chunk_size,
        "expected_chunks": expected_chunks,
    }


def to_file_response(file: FileModel) -> FileResponseSchema:
    thumb_url = f"/api/files/{file.id}/thumbnail" if file.thumbnail_path else None
    return FileResponseSchema(
        id=file.id,
        name=file.name,
        type=file.type,
        mime_type=file.mime_type,
        size=file.size,
        path=parse_path(file.path),
        is_starred=file.is_starred,
        is_trashed=file.is_trashed,
        thumbnail_url=thumb_url,
        created_at=file.created_at,
        updated_at=file.updated_at,
    )


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
        query = query.where(
            FileModel.path.in_(get_serialized_path_variants(parse_path(path)))
        )
    
    result = await db.execute(query.order_by(FileModel.type, FileModel.name))
    files = result.scalars().all()

    return [to_file_response(file) for file in files]


@router.get("/search", response_model=List[SearchResult])
async def search_files(
    q: str = Query(..., min_length=1, description="Search query"),
    file_type: Optional[str] = Query(None, alias="type"),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    starred_only: bool = Query(False),
    include_trashed: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search files by name, path metadata, and indexed text content."""
    normalized_query = q.strip()
    if not normalized_query:
        return []

    # Escape LIKE metacharacters so the query is treated as a literal substring.
    escaped_query = escape_like_literal(normalized_query)
    like_query = f"%{escaped_query}%"
    conditions = [
        FileModel.owner_id == current_user.id,
        or_(
            FileModel.name.ilike(like_query, escape=LIKE_ESCAPE_CHAR),
            FileModel.path.ilike(like_query, escape=LIKE_ESCAPE_CHAR),
            FileModel.mime_type.ilike(like_query, escape=LIKE_ESCAPE_CHAR),
            FileModel.type.ilike(like_query, escape=LIKE_ESCAPE_CHAR),
            FileModel.content_index.ilike(like_query, escape=LIKE_ESCAPE_CHAR),
        ),
    ]

    if not include_trashed:
        conditions.append(FileModel.is_trashed == False)
    if starred_only:
        conditions.append(FileModel.is_starred == True)
    if file_type:
        conditions.append(FileModel.type == file_type)
    if date_from:
        conditions.append(FileModel.created_at >= date_from)
    if date_to:
        conditions.append(FileModel.created_at <= date_to)

    result = await db.execute(
        select(FileModel)
        .where(and_(*conditions))
        .order_by((FileModel.type == "folder").desc(), FileModel.updated_at.desc(), FileModel.name.asc())
    )
    files = result.scalars().all()

    response = []
    for file in files:
        path_segments = parse_path(file.path)
        thumb_url = f"/api/files/{file.id}/thumbnail" if file.thumbnail_path else None
        response.append(SearchResult(
            id=file.id,
            name=file.name,
            type=file.type,
            mime_type=file.mime_type,
            size=file.size,
            path=path_segments,
            is_starred=file.is_starred,
            is_trashed=file.is_trashed,
            thumbnail_url=thumb_url,
            created_at=file.created_at,
            updated_at=file.updated_at,
            match_context=build_match_context(file, normalized_query, path_segments),
        ))

    return response


@router.post("/upload", response_model=List[FileResponseSchema], status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def upload_files(
    request: Request,
    files: List[UploadFile] = File(...),
    path: Optional[str] = Query("[]", description="Path as JSON array"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Upload one or more files (streamed to disk in chunks to avoid OOM)"""
    # Ensure storage directory exists
    user_storage_path = os.path.join(settings.storage_path, current_user.id)
    os.makedirs(user_storage_path, exist_ok=True)
    
    uploaded_files = []
    
    for file in files:
        safe_filename = sanitize_filename(file.filename)

        # Generate unique filename
        file_id = str(uuid.uuid4())
        ext = safe_filename.split('.')[-1] if '.' in safe_filename else ''
        storage_filename = f"{file_id}.{ext}" if ext else file_id
        storage_filepath = os.path.join(user_storage_path, storage_filename)
        
        # Stream file to disk in chunks (never load entire file into RAM)
        file_size = 0
        try:
            async with aiofiles.open(storage_filepath, 'wb') as f:
                while True:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    file_size += len(chunk)
                    await f.write(chunk)
                    
                    # Per-file size limit check
                    if settings.max_file_size_bytes > 0 and file_size > settings.max_file_size_bytes:
                        await f.close()
                        os.remove(storage_filepath)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File '{safe_filename}' exceeds max size of {settings.max_file_size_bytes} bytes"
                        )
        except HTTPException:
            raise
        except Exception as e:
            if os.path.exists(storage_filepath):
                os.remove(storage_filepath)
            raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
        
        # Check storage quota after writing
        if current_user.storage_quota > 0 and current_user.storage_used + file_size > current_user.storage_quota:
            os.remove(storage_filepath)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Storage quota exceeded. Available: {current_user.storage_quota - current_user.storage_used} bytes"
            )
        
        # Get mime type
        mime_type = file.content_type or mimetypes.guess_type(safe_filename)[0]
        
        # Generate thumbnail for images
        thumb_path = None
        if can_generate_thumbnail(safe_filename):
            thumb_dir = os.path.join(user_storage_path, "thumbnails")
            thumb_path = generate_thumbnail(storage_filepath, thumb_dir, file_id)
        
        # Create database entry with explicit defaults
        now = datetime.now(timezone.utc)
        new_file = FileModel(
            id=file_id,
            name=safe_filename,
            type=get_file_type(safe_filename, mime_type),
            mime_type=mime_type,
            size=file_size,
            path=normalize_path(path),
            storage_path=storage_filepath,
            content_index=build_search_document(storage_filepath, safe_filename, mime_type, get_file_type(safe_filename, mime_type)),
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
            file_name=safe_filename,
        )
        db.add(activity)
        
        uploaded_files.append(to_file_response(new_file))
    
    await db.flush()
    return uploaded_files


# --- CHUNKED UPLOAD ENDPOINTS ---

@router.post("/upload/init", response_model=ChunkedUploadInitResponse)
@limiter.limit("20/minute")
async def init_chunked_upload(
    request: Request,
    init_req: ChunkedUploadInitRequest,
    current_user: User = Depends(get_current_user),
):
    """Initialize a resumable chunked upload."""
    # Check overall storage quota before starting
    if current_user.storage_quota > 0 and current_user.storage_used + init_req.total_size > current_user.storage_quota:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Storage quota exceeded. Available: {current_user.storage_quota - current_user.storage_used} bytes"
        )

    # Per-file size limit check
    if settings.max_file_size_bytes > 0 and init_req.total_size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds max size of {settings.max_file_size_bytes} bytes"
        )

    upload_id = str(uuid.uuid4())
    temp_dir = get_upload_temp_dir(current_user.id, upload_id)
    os.makedirs(temp_dir, exist_ok=True)
    await write_upload_metadata(temp_dir, init_req.total_size, RESUMABLE_CHUNK_SIZE)

    # Return the upload_id and standard chunk size (e.g. 5 MB)
    return ChunkedUploadInitResponse(
        upload_id=upload_id,
        chunk_size=RESUMABLE_CHUNK_SIZE,
    )


@router.post("/upload/{upload_id}/chunk")
@limiter.limit("120/minute")
async def upload_chunk(
    request: Request,
    upload_id: str,
    chunk_index: int = Query(..., description="0-based index of the chunk"),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload a single chunk for a resumable upload."""
    upload_id = validate_upload_id(upload_id)
    temp_dir = get_upload_temp_dir(current_user.id, upload_id)
    
    if not os.path.exists(temp_dir):
        raise HTTPException(status_code=404, detail="Upload session not found or expired")

    metadata = await read_upload_metadata(temp_dir)
    expected_chunk_size = get_expected_chunk_size(
        metadata["total_size"],
        metadata["chunk_size"],
        chunk_index,
    )
    chunk_filepath = os.path.join(temp_dir, f"chunk_{chunk_index}")
    
    try:
        bytes_written = 0
        async with aiofiles.open(chunk_filepath, 'wb') as f:
            while True:
                data = await file.read(CHUNK_SIZE)
                if not data:
                    break
                bytes_written += len(data)
                if bytes_written > expected_chunk_size:
                    raise HTTPException(status_code=400, detail="Chunk exceeds declared upload size")
                await f.write(data)
    except HTTPException:
        if os.path.exists(chunk_filepath):
            os.remove(chunk_filepath)
        raise
    except Exception as e:
        if os.path.exists(chunk_filepath):
            os.remove(chunk_filepath)
        raise HTTPException(status_code=500, detail=f"Failed to save chunk: {e}")

    uploaded_bytes = 0
    for name in os.listdir(temp_dir):
        if not name.startswith("chunk_"):
            continue
        uploaded_bytes += os.path.getsize(os.path.join(temp_dir, name))
    if uploaded_bytes > metadata["total_size"]:
        if os.path.exists(chunk_filepath):
            os.remove(chunk_filepath)
        raise HTTPException(status_code=400, detail="Uploaded chunks exceed declared file size")

    return {"status": "ok", "message": f"Chunk {chunk_index} received"}


@router.post("/upload/complete", response_model=FileResponseSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def complete_chunked_upload(
    request: Request,
    complete_req: ChunkedUploadCompleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Complete a chunked upload by assembling chunks into the final file."""
    upload_id = validate_upload_id(complete_req.upload_id)
    temp_dir = get_upload_temp_dir(current_user.id, upload_id)
    
    if not os.path.exists(temp_dir):
        raise HTTPException(status_code=404, detail="Upload session not found")

    metadata = await read_upload_metadata(temp_dir)
    if complete_req.total_size != metadata["total_size"]:
        raise HTTPException(status_code=400, detail="Upload metadata does not match declared file size")

    user_storage_path = os.path.join(settings.storage_path, current_user.id)
    os.makedirs(user_storage_path, exist_ok=True)

    safe_filename = sanitize_filename(complete_req.filename)
    file_id = str(uuid.uuid4())
    ext = safe_filename.split('.')[-1] if '.' in safe_filename else ''
    storage_filename = f"{file_id}.{ext}" if ext else file_id
    final_storage_filepath = os.path.join(user_storage_path, storage_filename)

    chunk_indices = []
    for name in os.listdir(temp_dir):
        if not name.startswith("chunk_"):
            continue
        try:
            chunk_indices.append(int(name.split("_", 1)[1]))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Upload session metadata is invalid") from exc

    expected_indices = list(range(metadata["expected_chunks"]))
    if sorted(chunk_indices) != expected_indices:
        raise HTTPException(status_code=400, detail="Upload is incomplete")

    chunk_files = [f"chunk_{index}" for index in expected_indices]
    for index, chunk_filename in enumerate(chunk_files):
        chunk_path = os.path.join(temp_dir, chunk_filename)
        if os.path.getsize(chunk_path) != get_expected_chunk_size(
            metadata["total_size"],
            metadata["chunk_size"],
            index,
        ):
            raise HTTPException(status_code=400, detail="Upload is incomplete")

    assembled_size = 0
    try:
        async with aiofiles.open(final_storage_filepath, 'wb') as outfile:
            for chunk_filename in chunk_files:
                chunk_path = os.path.join(temp_dir, chunk_filename)
                async with aiofiles.open(chunk_path, 'rb') as infile:
                    # Write in blocks
                    while True:
                        data = await infile.read(65536)
                        if not data:
                            break
                        await outfile.write(data)
                        assembled_size += len(data)
    except Exception:
        if os.path.exists(final_storage_filepath):
            os.remove(final_storage_filepath)
        logger.exception("Failed to assemble file during chunk assembly")
        raise HTTPException(status_code=500, detail="Failed to assemble file.")

    # Clean up temp dir
    import shutil
    try:
        await asyncio.to_thread(shutil.rmtree, temp_dir, ignore_errors=True)
    except Exception as e:
        print(f"Warning: Failed to cleanup temp dir {temp_dir}: {e}")

    # Verify size
    if assembled_size != metadata["total_size"]:
        os.remove(final_storage_filepath)
        raise HTTPException(
            status_code=400,
            detail=f"Size mismatch: Expected {metadata['total_size']}, got {assembled_size}. File deleted."
        )

    # Enforce maximum allowed file size on the assembled file
    if settings.max_file_size_bytes and assembled_size > settings.max_file_size_bytes:
        os.remove(final_storage_filepath)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of {settings.max_file_size_bytes} bytes."
        )

    # Re-check storage quota (just in case it changed during upload)
    if current_user.storage_quota > 0 and current_user.storage_used + assembled_size > current_user.storage_quota:
        os.remove(final_storage_filepath)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Storage quota exceeded."
        )

    # Guess mime type if not provided
    mime_type = complete_req.mime_type or mimetypes.guess_type(safe_filename)[0]

    # Generate thumbnail
    thumb_path = None
    if can_generate_thumbnail(safe_filename):
        thumb_dir = os.path.join(user_storage_path, "thumbnails")
        thumb_path = generate_thumbnail(final_storage_filepath, thumb_dir, file_id)

    # Create DB entry
    now = datetime.now(timezone.utc)
    new_file = FileModel(
        id=file_id,
        name=safe_filename,
        type=get_file_type(safe_filename, mime_type),
        mime_type=mime_type,
        size=assembled_size,
        path=normalize_path(serialize_path(complete_req.path)),
        storage_path=final_storage_filepath,
        thumbnail_path=thumb_path,
        owner_id=current_user.id,
        is_starred=False,
        is_trashed=False,
        created_at=now,
        updated_at=now,
    )
    
    db.add(new_file)
    current_user.storage_used += assembled_size
    
    activity = ActivityLog(
        user_id=current_user.id,
        action="upload",
        file_name=safe_filename,
    )
    db.add(activity)
    
    await db.flush()

    thumb_url = f"/api/files/{new_file.id}/thumbnail" if new_file.thumbnail_path else None
    return FileResponseSchema(
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
    )


@router.get("/{file_id}/download")
@limiter.limit("60/minute")
async def download_file(
    request: Request,
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
    
    # Path traversal protection
    resolved = os.path.realpath(file.storage_path)
    base_path = os.path.realpath(settings.storage_path)
    if os.path.commonpath([base_path, resolved]) != base_path:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="download",
        file_name=file.name,
    )
    db.add(activity)
    await db.flush()
    
    file_size = os.path.getsize(file.storage_path)

    def iter_file():
        with open(file.storage_path, "rb") as f:
            while True:
                chunk = f.read(65536)  # 64KB chunks
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type=file.mime_type or "application/octet-stream",
        headers={
            "Content-Length": str(file_size),
            "Content-Disposition": build_content_disposition("attachment", file.name),
        }
    )


@router.post("/{file_id}/copy", response_model=FileResponseSchema, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def copy_file(
    request: Request,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Copy a file (creates a duplicate with '(copy)' suffix)"""
    import shutil

    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.owner_id == current_user.id)
        )
    )
    original = result.scalar_one_or_none()

    if not original:
        raise HTTPException(status_code=404, detail="File not found")

    if original.type == "folder":
        raise HTTPException(status_code=400, detail="Folder copy is not supported")

    if not original.storage_path or not os.path.exists(original.storage_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Check storage quota
    if current_user.storage_quota > 0 and current_user.storage_used + original.size > current_user.storage_quota:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Storage quota exceeded. Available: {current_user.storage_quota - current_user.storage_used} bytes"
        )

    # Generate new file ID and storage path
    new_id = str(uuid.uuid4())
    user_storage_path = os.path.join(settings.storage_path, current_user.id)
    ext = original.name.split('.')[-1] if '.' in original.name else ''
    storage_filename = f"{new_id}.{ext}" if ext else new_id
    new_storage_path = os.path.join(user_storage_path, storage_filename)

    # Copy file on disk
    try:
        await asyncio.to_thread(shutil.copy2, original.storage_path, new_storage_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to copy file: {e}")

    # Generate copy name: "file.txt" -> "file (copy).txt"
    base_name = original.name
    if '.' in base_name:
        name_part, ext_part = base_name.rsplit('.', 1)
        copy_name = f"{name_part} (copy).{ext_part}"
    else:
        copy_name = f"{base_name} (copy)"

    # Generate thumbnail for the copy
    thumb_path = None
    if can_generate_thumbnail(copy_name):
        thumb_dir = os.path.join(user_storage_path, "thumbnails")
        thumb_path = generate_thumbnail(new_storage_path, thumb_dir, new_id)

    # Create database entry
    now = datetime.now(timezone.utc)
    new_file = FileModel(
        id=new_id,
        name=copy_name,
        type=original.type,
        mime_type=original.mime_type,
        size=original.size,
        path=original.path,
        storage_path=new_storage_path,
        content_index=original.content_index,
        thumbnail_path=thumb_path,
        owner_id=current_user.id,
        is_starred=False,
        is_trashed=False,
        created_at=now,
        updated_at=now,
    )

    db.add(new_file)
    current_user.storage_used += original.size

    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="copy",
        file_name=copy_name,
    )
    db.add(activity)
    await db.flush()

    return to_file_response(new_file)


@router.patch("/{file_id}", response_model=FileResponseSchema)
@limiter.limit("60/minute")
async def update_file(
    request: Request,
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
    
    file.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(file)
    
    return to_file_response(file)


@router.post("/{file_id}/trash", response_model=FileResponseSchema)
@limiter.limit("30/minute")
async def trash_file(
    request: Request,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Move file or folder to trash (recursive for folders)"""
    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.owner_id == current_user.id)
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    now = datetime.now(timezone.utc)
    file.is_trashed = True
    file.trashed_at = now
    file.updated_at = now
    
    # If folder, recursively trash all children
    if file.type == "folder":
        folder_path = parse_path(file.path) + [file.name]
        folder_path_prefixes = get_serialized_path_prefixes(folder_path)
        children_result = await db.execute(
            select(FileModel).where(
                and_(
                    FileModel.owner_id == current_user.id,
                    or_(*[FileModel.path.like(prefix) for prefix in folder_path_prefixes]),
                    FileModel.is_trashed == False,
                )
            )
        )
        for child in children_result.scalars().all():
            child.is_trashed = True
            child.trashed_at = now
    
    activity = ActivityLog(
        user_id=current_user.id,
        action="trash",
        file_name=file.name,
    )
    db.add(activity)
    
    await db.flush()
    await db.refresh(file)
    
    return to_file_response(file)


@router.post("/{file_id}/restore", response_model=FileResponseSchema)
@limiter.limit("30/minute")
async def restore_file(
    request: Request,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Restore file or folder from trash (recursive for folders)"""
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
    file.updated_at = datetime.now(timezone.utc)
    
    # If folder, recursively restore all children
    if file.type == "folder":
        folder_path = parse_path(file.path) + [file.name]
        folder_path_prefixes = get_serialized_path_prefixes(folder_path)
        children_result = await db.execute(
            select(FileModel).where(
                and_(
                    FileModel.owner_id == current_user.id,
                    or_(*[FileModel.path.like(prefix) for prefix in folder_path_prefixes]),
                    FileModel.is_trashed == True,
                )
            )
        )
        for child in children_result.scalars().all():
            child.is_trashed = False
            child.trashed_at = None
    
    activity = ActivityLog(
        user_id=current_user.id,
        action="restore",
        file_name=file.name,
    )
    db.add(activity)
    
    await db.flush()
    await db.refresh(file)
    
    return to_file_response(file)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("20/minute")
async def delete_file_permanently(
    request: Request,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Permanently delete a file or folder (recursive for folders)"""
    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.owner_id == current_user.id)
        )
    )
    file = result.scalar_one_or_none()
    
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # If folder, recursively delete all children first
    if file.type == "folder":
        folder_path = parse_path(file.path) + [file.name]
        folder_path_prefixes = get_serialized_path_prefixes(folder_path)
        children_result = await db.execute(
            select(FileModel).where(
                and_(
                    FileModel.owner_id == current_user.id,
                    or_(*[FileModel.path.like(prefix) for prefix in folder_path_prefixes]),
                )
            )
        )
        for child in children_result.scalars().all():
            # Delete child's disk file
            if child.storage_path and os.path.exists(child.storage_path):
                os.remove(child.storage_path)
            # Delete child's thumbnail
            if child.thumbnail_path and os.path.exists(child.thumbnail_path):
                os.remove(child.thumbnail_path)
            # Update storage
            current_user.storage_used -= child.size
            await db.delete(child)
    
    # Delete the file/folder itself from disk
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


PREVIEWABLE_TYPES = {"image", "video", "pdf", "text"}


@router.get("/{file_id}/preview", response_model=None)
@limiter.limit("120/minute")
async def preview_file(
    request: Request,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Serve file content inline for preview. Authenticated via Authorization header."""

    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == file_id, FileModel.owner_id == current_user.id)
        )
    )
    file = result.scalar_one_or_none()

    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if file.type not in PREVIEWABLE_TYPES:
        raise HTTPException(status_code=400, detail="This file type cannot be previewed")

    if not file.storage_path or not os.path.exists(file.storage_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Path traversal protection
    resolved = os.path.realpath(file.storage_path)
    base_path = os.path.realpath(settings.storage_path)
    if os.path.commonpath([base_path, resolved]) != base_path:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get file size
    file_size = os.path.getsize(file.storage_path)
    media_type = file.mime_type or mimetypes.guess_type(file.name)[0] or "application/octet-stream"

    # Parse Range header for partial content (required for video seeking)
    range_header = request.headers.get("range")

    if range_header:
        # Parse "bytes=start-end"
        try:
            range_spec = range_header.replace("bytes=", "").strip()
            parts = range_spec.split("-")
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if parts[1] else file_size - 1
        except (ValueError, IndexError):
            start = 0
            end = file_size - 1

        if start >= file_size:
            return StreamingResponse(
                status_code=416,
                headers={"Content-Range": f"bytes */{file_size}"}
            )
        end = min(end, file_size - 1)
        content_length = end - start + 1

        def iter_range():
            with open(file.storage_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(65536, remaining)  # 64KB chunks
                    data = f.read(chunk_size)
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            iter_range(),
            status_code=206,
            media_type=media_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Content-Length": str(content_length),
                "Accept-Ranges": "bytes",
                "Content-Disposition": build_content_disposition("inline", file.name),
                "Cache-Control": "private, max-age=3600",
            }
        )

    # No Range header — stream the full file in chunks (avoids loading into memory)
    def iter_file():
        with open(file.storage_path, "rb") as f:
            while True:
                chunk = f.read(65536)  # 64KB chunks
                if not chunk:
                    break
                yield chunk

    return StreamingResponse(
        iter_file(),
        media_type=media_type,
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Content-Disposition": build_content_disposition("inline", file.name),
            "Cache-Control": "private, max-age=3600",
        }
    )


@router.get("/{file_id}/thumbnail", response_model=None)
@limiter.limit("120/minute")
async def get_thumbnail(
    request: Request,
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Serve a file's thumbnail image. Authenticated via Authorization header."""
    
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
    
    # Path traversal protection
    resolved = os.path.realpath(file.thumbnail_path)
    base_path = os.path.realpath(settings.storage_path)
    if os.path.commonpath([base_path, resolved]) != base_path:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return FileResponse(
        path=file.thumbnail_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"}
    )
