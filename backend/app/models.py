"""
Home Cloud Drive - SQLAlchemy Models
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import secrets

from app.database import Base


def generate_uuid():
    return str(uuid.uuid4())


def generate_share_token():
    return secrets.token_urlsafe(32)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False)
    storage_used = Column(BigInteger, default=0)  # bytes
    storage_quota = Column(BigInteger, default=107374182400)  # 100 GB
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    files = relationship("File", back_populates="owner", cascade="all, delete-orphan")


class File(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # folder, pdf, image, video, text, archive, etc.
    mime_type = Column(String(100), nullable=True)
    size = Column(BigInteger, default=0)  # bytes
    path = Column(Text, default="[]")  # JSON array of folder names
    storage_path = Column(String(500), nullable=True)  # actual file path on disk
    
    # Search & thumbnails
    content_index = Column(Text, nullable=True)  # extracted text for full-text search
    thumbnail_path = Column(String(500), nullable=True)  # path to generated thumbnail
    
    # Ownership
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="files")
    
    # Status flags
    is_starred = Column(Boolean, default=False)
    is_trashed = Column(Boolean, default=False)
    trashed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ShareLink(Base):
    __tablename__ = "share_links"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    token = Column(String(64), unique=True, nullable=False, default=generate_share_token, index=True)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    permission = Column(String(20), default="view")  # view | download
    password_hash = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    max_downloads = Column(Integer, nullable=True)
    download_count = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    file = relationship("File")
    owner = relationship("User")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # upload, download, rename, trash, etc.
    file_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
