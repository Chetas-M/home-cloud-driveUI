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
