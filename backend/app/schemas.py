"""
Home Cloud Drive - Pydantic Schemas
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List


# ============ AUTH SCHEMAS ============

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    is_admin: bool = False
    storage_used: int
    storage_quota: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None


# ============ FILE SCHEMAS ============

class FileBase(BaseModel):
    name: str
    type: str
    size: int = 0
    path: List[str] = []


class FileCreate(BaseModel):
    name: str
    path: List[str] = []


class FileResponse(BaseModel):
    id: str
    name: str
    type: str
    mime_type: Optional[str] = None
    size: int
    path: List[str]
    is_starred: bool
    is_trashed: bool
    thumbnail_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FileUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[List[str]] = None
    is_starred: Optional[bool] = None


class FileMoveRequest(BaseModel):
    new_path: List[str]


# ============ FOLDER SCHEMAS ============

class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    path: List[str] = []


# ============ STORAGE SCHEMAS ============

class StorageBreakdown(BaseModel):
    type: str
    size: int
    count: int


class StorageResponse(BaseModel):
    used: int
    quota: int
    percent_used: float
    breakdown: List[StorageBreakdown]
    disk_total: int = 0
    disk_free: int = 0


# ============ ACTIVITY SCHEMAS ============

class ActivityResponse(BaseModel):
    action: str
    file_name: str
    timestamp: datetime

    class Config:
        from_attributes = True


# ============ ADMIN SCHEMAS ============

class AdminUserResponse(BaseModel):
    id: str
    email: str
    username: str
    is_admin: bool
    storage_used: int
    storage_quota: int
    file_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserUpdate(BaseModel):
    storage_quota: Optional[int] = None
    is_admin: Optional[bool] = None
    username: Optional[str] = None
    email: Optional[EmailStr] = None


class SystemStats(BaseModel):
    total_users: int
    total_files: int
    total_storage_used: int
    total_storage_quota: int
    disk_total: int = 0
    disk_free: int = 0


# ============ SHARING SCHEMAS ============

class ShareLinkCreate(BaseModel):
    file_id: str
    permission: str = "view"  # view | download
    password: Optional[str] = None
    expires_in_hours: Optional[int] = None
    max_downloads: Optional[int] = None


class ShareLinkResponse(BaseModel):
    id: str
    token: str
    file_id: str
    file_name: str = ""
    permission: str
    has_password: bool = False
    expires_at: Optional[datetime] = None
    max_downloads: Optional[int] = None
    download_count: int = 0
    is_active: bool
    created_at: datetime
    share_url: str = ""

    class Config:
        from_attributes = True


# ============ SEARCH SCHEMAS ============

class SearchResult(FileResponse):
    match_context: Optional[str] = None
