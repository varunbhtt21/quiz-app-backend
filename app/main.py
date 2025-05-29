from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.core.config import settings
from app.core.database import create_db_and_tables
from app.api import auth, course, contest, export, student
from app.routers import mcq

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create uploads directory if it doesn't exist
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# Mount the uploads directory
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Include API routers
app.include_router(auth.router, prefix="/api")
app.include_router(mcq.router, prefix="/api")
app.include_router(course.router, prefix="/api")
app.include_router(contest.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(student.router, prefix="/api/students", tags=["Students"])


@app.on_event("startup")
def on_startup():
    """Initialize database on startup"""
    create_db_and_tables()


@app.get("/")
def read_root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.app_version,
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"} 