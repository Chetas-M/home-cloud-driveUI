"""
Home Cloud Drive - SQLAlchemy Models
"""
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, BigInteger, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
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
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(64), nullable=True)
    two_factor_pending_secret = Column(String(64), nullable=True)
    is_admin = Column(Boolean, default=False)
    storage_used = Column(BigInteger, default=0)  # bytes
    storage_quota = Column(BigInteger, default=107374182400)  # 100 GB
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    files = relationship("File", back_populates="owner", cascade="all, delete-orphan")
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    shared_folder_accesses = relationship(
        "SharedFolderAccess",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="SharedFolderAccess.user_id",
    )


class File(Base):
    __tablename__ = "files"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)  # folder, pdf, image, video, text, archive, etc.
    mime_type = Column(String(100), nullable=True)
    size = Column(BigInteger, default=0)  # bytes
    path = Column(Text, default="[]")  # JSON array of folder names
    storage_path = Column(String(500), nullable=True)  # actual file path on disk
    version = Column(Integer, default=1)
    
    # Search & thumbnails
    content_index = Column(Text, nullable=True)  # extracted text for full-text search
    thumbnail_path = Column(String(500), nullable=True)  # path to generated thumbnail
    
    # Ownership
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="files")
    versions = relationship("FileVersion", back_populates="file", cascade="all, delete-orphan", order_by="FileVersion.version")
    
    # Status flags
    is_starred = Column(Boolean, default=False)
    is_trashed = Column(Boolean, default=False)
    trashed_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class FileVersion(Base):
    __tablename__ = "file_versions"
    __table_args__ = (
        UniqueConstraint("file_id", "version", name="uq_file_versions_file_id_version"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    size = Column(BigInteger, default=0)
    mime_type = Column(String(100), nullable=True)
    storage_path = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)

    file = relationship("File", back_populates="versions")
    owner = relationship("User")


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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    file = relationship("File")
    owner = relationship("User")


class SharedFolderAccess(Base):
    __tablename__ = "shared_folders"
    __table_args__ = (
        UniqueConstraint("folder_id", "user_id", name="uq_shared_folders_folder_user"),
    )

    id = Column(String(36), primary_key=True, default=generate_uuid)
    folder_id = Column(String(36), ForeignKey("files.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False, default="viewer")  # viewer | editor | admin
    invited_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    folder = relationship("File")
    owner = relationship("User", foreign_keys=[owner_id])
    user = relationship("User", back_populates="shared_folder_accesses", foreign_keys=[user_id])
    invited_by_user = relationship("User", foreign_keys=[invited_by])


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # upload, download, rename, trash, etc.
    file_name = Column(String(255), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(Text, nullable=True)
    device_name = Column(String(255), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_seen_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    revoked_at = Column(DateTime, nullable=True)
    is_suspicious = Column(Boolean, default=False)

    user = relationship("User", back_populates="sessions")
