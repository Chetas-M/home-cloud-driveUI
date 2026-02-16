"""
Home Cloud Drive - Sharing Router
Provides endpoints for creating and accessing shared file links.
"""
import os
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.database import get_db
from app.models import User, File as FileModel, ShareLink, ActivityLog
from app.schemas import ShareLinkCreate, ShareLinkResponse
from app.auth import get_current_user, get_password_hash, verify_password
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/api/share", tags=["Sharing"])


@router.post("", response_model=ShareLinkResponse, status_code=status.HTTP_201_CREATED)
async def create_share_link(
    data: ShareLinkCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a share link for a file"""
    # Verify file exists and belongs to user
    result = await db.execute(
        select(FileModel).where(
            and_(FileModel.id == data.file_id, FileModel.owner_id == current_user.id)
        )
    )
    file = result.scalar_one_or_none()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if file.type == "folder":
        raise HTTPException(status_code=400, detail="Cannot share folders directly")

    # Build share link
    share_link = ShareLink(
        file_id=data.file_id,
        owner_id=current_user.id,
        permission=data.permission,
    )

    if data.password:
        share_link.password_hash = get_password_hash(data.password)

    if data.expires_in_hours:
        share_link.expires_at = datetime.utcnow() + timedelta(hours=data.expires_in_hours)

    if data.max_downloads:
        share_link.max_downloads = data.max_downloads

    db.add(share_link)

    # Log activity
    activity = ActivityLog(
        user_id=current_user.id,
        action="share",
        file_name=file.name,
    )
    db.add(activity)

    await db.flush()
    await db.refresh(share_link)

    return ShareLinkResponse(
        id=share_link.id,
        token=share_link.token,
        file_id=share_link.file_id,
        file_name=file.name,
        permission=share_link.permission,
        has_password=share_link.password_hash is not None,
        expires_at=share_link.expires_at,
        max_downloads=share_link.max_downloads,
        download_count=share_link.download_count,
        is_active=share_link.is_active,
        created_at=share_link.created_at,
        share_url=f"/shared/{share_link.token}",
    )


@router.get("/my-links", response_model=List[ShareLinkResponse])
async def get_my_share_links(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List current user's share links"""
    result = await db.execute(
        select(ShareLink, FileModel.name)
        .join(FileModel, ShareLink.file_id == FileModel.id)
        .where(ShareLink.owner_id == current_user.id)
        .order_by(ShareLink.created_at.desc())
    )

    links = []
    for row in result:
        link = row[0]
        file_name = row[1]
        links.append(ShareLinkResponse(
            id=link.id,
            token=link.token,
            file_id=link.file_id,
            file_name=file_name,
            permission=link.permission,
            has_password=link.password_hash is not None,
            expires_at=link.expires_at,
            max_downloads=link.max_downloads,
            download_count=link.download_count,
            is_active=link.is_active,
            created_at=link.created_at,
            share_url=f"/shared/{link.token}",
        ))
    return links


@router.get("/{token}")
async def access_shared_file(
    token: str,
    password: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Access a shared file (public — no auth required)"""
    result = await db.execute(
        select(ShareLink, FileModel)
        .join(FileModel, ShareLink.file_id == FileModel.id)
        .where(ShareLink.token == token)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Share link not found")

    link, file = row[0], row[1]

    # Check if active
    if not link.is_active:
        raise HTTPException(status_code=410, detail="This share link has been revoked")

    # Check expiry
    if link.expires_at and datetime.utcnow() > link.expires_at:
        raise HTTPException(status_code=410, detail="This share link has expired")

    # Check max downloads
    if link.max_downloads and link.download_count >= link.max_downloads:
        raise HTTPException(status_code=410, detail="Download limit reached")

    # Check password
    if link.password_hash:
        if not password:
            raise HTTPException(
                status_code=401,
                detail="Password required",
                headers={"X-Share-Password-Required": "true"},
            )
        if not verify_password(password, link.password_hash):
            raise HTTPException(status_code=401, detail="Incorrect password")

    # Return file info for view permission
    return {
        "file_name": file.name,
        "file_type": file.type,
        "file_size": file.size,
        "mime_type": file.mime_type,
        "permission": link.permission,
        "can_download": link.permission == "download",
    }


@router.get("/{token}/download")
async def download_shared_file(
    token: str,
    password: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Download a shared file"""
    result = await db.execute(
        select(ShareLink, FileModel)
        .join(FileModel, ShareLink.file_id == FileModel.id)
        .where(ShareLink.token == token)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Share link not found")

    link, file = row[0], row[1]

    # Validate
    if not link.is_active:
        raise HTTPException(status_code=410, detail="This share link has been revoked")
    if link.expires_at and datetime.utcnow() > link.expires_at:
        raise HTTPException(status_code=410, detail="This share link has expired")
    if link.max_downloads and link.download_count >= link.max_downloads:
        raise HTTPException(status_code=410, detail="Download limit reached")
    if link.permission != "download":
        raise HTTPException(status_code=403, detail="Download not permitted for this link")

    # Check password
    if link.password_hash:
        if not password or not verify_password(password, link.password_hash):
            raise HTTPException(status_code=401, detail="Password required or incorrect")

    # Check file on disk
    if not file.storage_path or not os.path.exists(file.storage_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Increment download count
    link.download_count += 1
    await db.flush()

    return FileResponse(
        path=file.storage_path,
        filename=file.name,
        media_type=file.mime_type or "application/octet-stream"
    )


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_share_link(
    link_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Revoke (deactivate) a share link"""
    result = await db.execute(
        select(ShareLink).where(
            and_(ShareLink.id == link_id, ShareLink.owner_id == current_user.id)
        )
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Share link not found")

    link.is_active = False
    await db.flush()
