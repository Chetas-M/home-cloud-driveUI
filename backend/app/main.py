"""
Home Cloud Drive - FastAPI Application Entry Point
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routers import auth, files, folders, storage

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[*] Starting Home Cloud Drive API...")
    
    # Create directories
    os.makedirs(settings.storage_path, exist_ok=True)
    os.makedirs("./data", exist_ok=True)
    
    # Initialize database
    await init_db()
    print("[+] Database initialized")
    
    yield
    
    # Shutdown
    print("[*] Shutting down Home Cloud Drive API...")


app = FastAPI(
    title="Home Cloud Drive API",
    description="Personal cloud storage backend with file management, user authentication, and storage tracking",
    version="1.0.0",
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

# Include routers
app.include_router(auth.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(storage.router)


@app.get("/")
async def root():
    return {
        "message": "Home Cloud Drive API",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
