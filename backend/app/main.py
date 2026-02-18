"""
Home Cloud Drive - FastAPI Application Entry Point
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db, engine
from app.routers import auth, files, folders, storage

settings = get_settings()


async def run_migrations():
    """Add new columns to existing tables (SQLite doesn't support IF NOT EXISTS for columns)"""
    from sqlalchemy import text
    
    migrations = [
        ("users", "is_admin", "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"),
        ("files", "content_index", "ALTER TABLE files ADD COLUMN content_index TEXT"),
        ("files", "thumbnail_path", "ALTER TABLE files ADD COLUMN thumbnail_path VARCHAR(500)"),
    ]
    
    async with engine.begin() as conn:
        for table, column, sql in migrations:
            try:
                await conn.execute(text(sql))
                print(f"[+] Added column {table}.{column}")
            except Exception:
                pass  # Column already exists


async def cleanup_old_trash():
    """Auto-delete files that have been in trash longer than trash_auto_delete_days."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, and_
    from app.database import async_session
    from app.models import File as FileModel, User
    
    days = settings.trash_auto_delete_days
    if days <= 0:
        return
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    async with async_session() as db:
        result = await db.execute(
            select(FileModel).where(
                and_(
                    FileModel.is_trashed == True,
                    FileModel.trashed_at != None,
                    FileModel.trashed_at < cutoff,
                )
            )
        )
        old_files = result.scalars().all()
        
        if not old_files:
            print(f"[*] Trash cleanup: no files older than {days} days")
            return
        
        # Group by owner for storage accounting
        owner_freed = {}
        deleted_count = 0
        
        for file in old_files:
            # Delete disk file
            if file.storage_path and os.path.exists(file.storage_path):
                os.remove(file.storage_path)
            # Delete thumbnail
            if file.thumbnail_path and os.path.exists(file.thumbnail_path):
                os.remove(file.thumbnail_path)
            
            owner_freed[file.owner_id] = owner_freed.get(file.owner_id, 0) + file.size
            await db.delete(file)
            deleted_count += 1
        
        # Update storage for each owner
        for owner_id, freed in owner_freed.items():
            user_result = await db.execute(select(User).where(User.id == owner_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.storage_used = max(0, user.storage_used - freed)
        
        await db.commit()
        print(f"[+] Trash cleanup: deleted {deleted_count} files older than {days} days")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[*] Starting Home Cloud Drive API...")
    
    # Create directories
    os.makedirs(settings.storage_path, exist_ok=True)
    os.makedirs("./data", exist_ok=True)
    
    # Initialize database (creates new tables)
    await init_db()
    print("[+] Database initialized")
    
    # Run migrations for new columns on existing tables
    await run_migrations()
    print("[+] Migrations complete")
    
    # Auto-cleanup old trashed files
    await cleanup_old_trash()
    
    yield
    
    # Shutdown
    print("[*] Shutting down Home Cloud Drive API...")


app = FastAPI(
    title="Home Cloud Drive API",
    description="Personal cloud storage backend with file management, user authentication, and storage tracking",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import additional routers
from app.routers import admin, sharing

# Include routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(storage.router)
app.include_router(admin.router)
app.include_router(sharing.router)


@app.get("/")
async def root():
    return {
        "message": "Home Cloud Drive API",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
