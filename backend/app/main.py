"""
Home Cloud Drive - FastAPI Application Entry Point
"""
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db, engine
from app.limiter import limiter
from app.routers import auth, files, folders, storage

settings = get_settings()


async def run_migrations():
    """Add new columns to existing tables (SQLite doesn't support IF NOT EXISTS for columns)"""
    from sqlalchemy import text
    
    migrations = [
        ("users", "is_admin", "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0"),
        ("users", "two_factor_enabled", "ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT 0"),
        ("users", "two_factor_secret", "ALTER TABLE users ADD COLUMN two_factor_secret VARCHAR(64)"),
        ("users", "two_factor_pending_secret", "ALTER TABLE users ADD COLUMN two_factor_pending_secret VARCHAR(64)"),
        ("files", "content_index", "ALTER TABLE files ADD COLUMN content_index TEXT"),
        ("files", "thumbnail_path", "ALTER TABLE files ADD COLUMN thumbnail_path VARCHAR(500)"),
        ("files", "version", "ALTER TABLE files ADD COLUMN version INTEGER DEFAULT 1"),
    ]
    
    async with engine.begin() as conn:
        for table, column, sql in migrations:
            try:
                await conn.execute(text(sql))
                print(f"[+] Added column {table}.{column}")
            except Exception:
                pass  # nosec B110

        # Ensure the unique index on (file_id, version) exists for existing databases
        try:
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_file_versions_file_id_version "
                "ON file_versions (file_id, version)"
            ))
            print("[+] Ensured unique index on file_versions(file_id, version)")
        except Exception:
            pass  # nosec B110


async def cleanup_old_trash():
    """Auto-delete files that have been in trash longer than trash_auto_delete_days."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, and_
    from app.database import async_session
    from app.models import File as FileModel, User, FileVersion
    
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
            freed = 0
            versions_result = await db.execute(
                select(FileVersion).where(FileVersion.file_id == file.id)
            )
            versions = versions_result.scalars().all()

            if versions:
                for version in versions:
                    if version.storage_path and os.path.exists(version.storage_path):
                        try:
                            os.remove(version.storage_path)
                        except OSError:
                            pass
                    freed += version.size or 0
                    await db.delete(version)
            else:
                if file.storage_path and os.path.exists(file.storage_path):
                    try:
                        os.remove(file.storage_path)
                    except OSError:
                        pass
                freed += file.size or 0

            # Delete thumbnail
            if file.thumbnail_path and os.path.exists(file.thumbnail_path):
                try:
                    os.remove(file.thumbnail_path)
                except OSError:
                    pass
            
            owner_freed[file.owner_id] = owner_freed.get(file.owner_id, 0) + freed
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


BACKFILL_BATCH_SIZE = 100


async def backfill_search_index():
    """Populate search indexes for existing files that predate indexing.

    Runs as a non-blocking background task.  Files are processed in batches of
    BACKFILL_BATCH_SIZE with a commit after every batch to keep individual
    transactions small.  A non-blocking exclusive file lock prevents multiple
    workers from running the backfill concurrently in multi-worker deployments.

    After processing, ``content_index`` is set to the extracted text, or to
    ``""`` (empty string) as a sentinel for "checked – nothing to index".
    Only rows with ``content_index IS NULL`` are treated as unprocessed, so
    binary files are not re-examined on every startup.
    """
    try:
        import fcntl as _fcntl
    except ImportError:
        # fcntl is not available on Windows; file locking is skipped on that platform.
        _fcntl = None
        print("[!] Search index backfill: fcntl unavailable, multi-worker lock disabled")

    from sqlalchemy import select
    from app.database import async_session
    from app.models import File as FileModel
    from app.search_index import build_search_document

    lock_path = "./data/.backfill.lock"
    lock_fd = None
    if _fcntl is not None:
        try:
            lock_fd = open(lock_path, "w")
            _fcntl.flock(lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        except BlockingIOError:
            print("[*] Search index backfill: another worker is already running, skipping")
            if lock_fd is not None:
                lock_fd.close()
            return
        except OSError as exc:
            print(f"[!] Search index backfill: could not acquire lock ({exc}), skipping")
            if lock_fd is not None:
                lock_fd.close()
            return

    try:
        total_updated = 0
        while True:
            async with async_session() as db:
                result = await db.execute(
                    select(FileModel)
                    .where(FileModel.content_index.is_(None))
                    .limit(BACKFILL_BATCH_SIZE)
                )
                files = result.scalars().all()

                if not files:
                    break

                for file in files:
                    indexed_content = await asyncio.to_thread(
                        build_search_document,
                        file.storage_path,
                        file.name,
                        file.mime_type,
                        file.type,
                    )
                    # Use "" as a sentinel for "checked, nothing to index" so
                    # these rows are not revisited on the next startup.
                    file.content_index = indexed_content or ""

                await db.commit()
                total_updated += len(files)

            # Yield to other async tasks between batches.
            await asyncio.sleep(0)

    finally:
        if lock_fd is not None and _fcntl is not None:
            _fcntl.flock(lock_fd, _fcntl.LOCK_UN)
            lock_fd.close()
        try:
            os.remove(lock_path)
        except OSError:
            pass

    if total_updated:
        print(f"[+] Search index backfill: updated {total_updated} files")
    else:
        print("[*] Search index backfill: no updates needed")


def _backfill_done_callback(task: asyncio.Task) -> None:
    """Log any unhandled exception from the backfill background task."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        print(f"[!] Search index backfill failed with unhandled exception: {exc!r}")


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

    # Populate missing content indexes as a non-blocking background task.
    # Store the reference on app.state so it can be awaited/cancelled on shutdown
    # and the done-callback surfaces any unexpected exceptions.
    backfill_task = asyncio.create_task(backfill_search_index())
    backfill_task.add_done_callback(_backfill_done_callback)
    app.state.backfill_task = backfill_task
    
    # Auto-cleanup old trashed files
    await cleanup_old_trash()
    
    yield
    
    # Shutdown — cancel the backfill if it is still running
    task = getattr(app.state, "backfill_task", None)
    if task is not None and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    print("[*] Shutting down Home Cloud Drive API...")


app = FastAPI(
    title="Home Cloud Drive API",
    description="Personal cloud storage backend",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None,      # Disable /docs in production
    redoc_url=None,      # Disable /redoc in production
    openapi_url=None,    # Disable /openapi.json
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Import additional routers
from app.routers import admin, sharing, shared_folders

# Include routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(storage.router)
app.include_router(admin.router)
app.include_router(sharing.router)
app.include_router(shared_folders.router)


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/health")
async def health_check(request: Request):
    """Health check — only responds to internal Docker health checks"""
    client_ip = request.client.host if request.client else ""
    if client_ip not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=404)
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)  # nosec B104
