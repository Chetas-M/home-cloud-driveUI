"""
Home Cloud Drive - Local Storage Service
Simple file storage using local filesystem with Docker volume support
"""
import os
import uuid
import aiofiles
from typing import Optional

from app.config import get_settings

settings = get_settings()


class LocalStorage:
    """Simple local filesystem storage"""
    
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)
    
    def _get_user_path(self, user_id: str) -> str:
        """Get or create user's storage directory"""
        user_path = os.path.join(self.base_path, user_id)
        os.makedirs(user_path, exist_ok=True)
        return user_path
    
    async def save(self, file_content: bytes, filename: str, user_id: str) -> str:
        """
        Save file to disk and return the storage path.
        Files are organized by user_id for easy management.
        """
        # Generate unique filename to avoid collisions
        file_id = str(uuid.uuid4())
        ext = filename.split('.')[-1] if '.' in filename else ''
        storage_filename = f"{file_id}.{ext}" if ext else file_id
        
        user_path = self._get_user_path(user_id)
        full_path = os.path.join(user_path, storage_filename)
        
        async with aiofiles.open(full_path, 'wb') as f:
            await f.write(file_content)
        
        return full_path
    
    async def get(self, storage_path: str) -> bytes:
        """Read file from disk"""
        if not os.path.exists(storage_path):
            raise FileNotFoundError(f"File not found: {storage_path}")
        
        async with aiofiles.open(storage_path, 'rb') as f:
            return await f.read()
    
    async def delete(self, storage_path: str) -> bool:
        """Delete file from disk"""
        if storage_path and os.path.exists(storage_path):
            os.remove(storage_path)
            return True
        return False
    
    def exists(self, storage_path: str) -> bool:
        """Check if file exists"""
        return storage_path and os.path.exists(storage_path)
    
    def get_file_path(self, storage_path: str) -> Optional[str]:
        """Get absolute file path for direct access (e.g., for streaming)"""
        if self.exists(storage_path):
            return os.path.abspath(storage_path)
        return None


# Global storage instance
_storage: Optional[LocalStorage] = None


def get_storage() -> LocalStorage:
    """Get or create storage singleton"""
    global _storage
    if _storage is None:
        _storage = LocalStorage(settings.storage_path)
    return _storage
