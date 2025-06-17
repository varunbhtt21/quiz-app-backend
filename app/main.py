from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.core.config import settings
from app.core.database import create_db_and_tables
from app.api import auth, course, contest, export, student, otpless_auth, tag, mcq, email, monitoring, submission_review

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,  # Use configurable CORS origins from settings
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: Image uploads are now handled by S3/Supabase storage service
# Local uploads directory and static file mounting removed in favor of cloud storage

# Mount static files for monitoring dashboard
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include API routers
app.include_router(auth.router, prefix="/api")
app.include_router(otpless_auth.router, prefix="/api")
app.include_router(mcq.router, prefix="/api")
app.include_router(tag.router, prefix="/api")
app.include_router(course.router, prefix="/api")
app.include_router(contest.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(student.router, prefix="/api/students", tags=["Students"])
app.include_router(submission_review.router, prefix="/api")  # Submission review endpoints
app.include_router(email.router)  # Email service endpoints
app.include_router(monitoring.router, prefix="/api")  # Monitoring endpoints


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


@app.get("/monitoring")
def monitoring_dashboard():
    """Redirect to monitoring dashboard"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/monitoring_dashboard.html") 