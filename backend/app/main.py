"""
RunbookIQ FastAPI application entry point.
"""
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import alerts, health, incidents, remediation, runbooks
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.redis import close_redis

configure_logging()
settings = get_settings()
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    log.info("runbookiq_starting", env=settings.app_env)

    # Ensure upload directory exists
    import os
    os.makedirs(settings.upload_dir, exist_ok=True)

    yield

    log.info("runbookiq_shutting_down")
    await close_redis()


app = FastAPI(
    title="RunbookIQ",
    description="AI-Powered Incident Triage & Runbook Assistant for DevOps Teams",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env != "production" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Routes
API_PREFIX = "/api/v1"
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(alerts.router, prefix=API_PREFIX)
app.include_router(incidents.router, prefix=API_PREFIX)
app.include_router(runbooks.router, prefix=API_PREFIX)
app.include_router(remediation.router, prefix=API_PREFIX)
