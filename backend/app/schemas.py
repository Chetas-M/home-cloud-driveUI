"""
Home Cloud Drive - Pydantic Schemas
"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal, Optional, List


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
    two_factor_enabled: bool = False
    storage_used: int
    storage_quota: int
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: Optional[str] = None
    token_type: str = "bearer"
    requires_2fa: bool = False
    temporary_token: Optional[str] = None


class TokenData(BaseModel):
    user_id: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)


class AdminPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6)


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class TwoFactorEnableRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class TwoFactorDisableRequest(BaseModel):
    password: str
    code: str = Field(..., min_length=6, max_length=6)


class TwoFactorLoginRequest(BaseModel):
    temporary_token: str
    code: str = Field(..., min_length=6, max_length=6)


class SessionResponse(BaseModel):
    id: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_name: Optional[str] = None
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    is_suspicious: bool = False
    is_current: bool = False

    class Config:
        from_attributes = True


# ============ FILE SCHEMAS ============

class FileBase(BaseModel):
    name: str
    type: str
    size: int = 0
    path: List[str] = Field(default_factory=list)


class FileCreate(BaseModel):
    name: str
    path: List[str] = Field(default_factory=list)


class ChunkedUploadInitRequest(BaseModel):
    filename: str
    total_size: int = Field(..., ge=0)
    path: List[str] = Field(default_factory=list)
    mime_type: Optional[str] = None
    shared_folder_id: Optional[str] = None


class ChunkedUploadInitResponse(BaseModel):
    upload_id: str
    chunk_size: int


class ChunkedUploadCompleteRequest(BaseModel):
    upload_id: str
    filename: str
    total_size: int = Field(..., ge=0)
    path: List[str] = Field(default_factory=list)
    mime_type: Optional[str] = None
    shared_folder_id: Optional[str] = None


class ChunkedUploadStatusResponse(BaseModel):
    upload_id: str
    filename: Optional[str] = None
    path: List[str] = Field(default_factory=list)
    mime_type: Optional[str] = None
    total_size: int
    chunk_size: int
    expected_chunks: int
    uploaded_chunks: List[int] = Field(default_factory=list)
    uploaded_bytes: int
    next_chunk_index: int


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
    version: int = 1
    is_shared: bool = False
    is_shared_root: bool = False
    shared_folder_id: Optional[str] = None
    access_role: Optional[str] = None
    owner_id: Optional[str] = None
    owner_username: Optional[str] = None
    can_write: bool = False
    can_manage: bool = False
    can_share_public: bool = False
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


class FileVersionResponse(BaseModel):
    id: str
    version: int
    size: int
    mime_type: Optional[str] = None
    created_at: datetime
    is_current: bool = False
    created_by: Optional[str] = None

    class Config:
        from_attributes = True


# ============ FOLDER SCHEMAS ============

class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    path: List[str] = Field(default_factory=list)
    shared_folder_id: Optional[str] = None


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
    permission: Literal["view", "download"] = "view"
    password: Optional[str] = None
    expires_in_hours: Optional[int] = Field(None, ge=1, le=24 * 365)
    max_downloads: Optional[int] = Field(None, ge=1)


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


class SharedFolderInviteCreate(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)
    role: Literal["viewer", "editor", "admin"] = "viewer"


class SharedFolderAccessUpdate(BaseModel):
    role: Literal["viewer", "editor", "admin"]


class SharedFolderAccessResponse(BaseModel):
    id: str
    folder_id: str
    role: str
    created_at: datetime
    updated_at: datetime
    user_id: str
    username: str
    email: str
    invited_by: Optional[str] = None


# ============ SEARCH SCHEMAS ============

class SearchResult(FileResponse):
    match_context: Optional[str] = None
