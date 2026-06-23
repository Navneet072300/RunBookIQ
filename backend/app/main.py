"""
RunbookIQ FastAPI application entry point.
"""
import asyncio
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
from app.ingestion.normaliser import normalise_and_deduplicate
from app.workers.tasks import enqueue_alert_processing

configure_logging()
settings = get_settings()
log = structlog.get_logger(__name__)


async def _k8s_ingest_callback(raw_event: dict, source: str = "kubernetes") -> None:
    """Called by the K8s watcher for each event; normalises and enqueues."""
    try:
        alerts_list = await normalise_and_deduplicate(
            raw_event, source=source, tenant_id=settings.default_tenant_id
        )
        for alert in alerts_list:
            enqueue_alert_processing(alert)
            log.info("k8s_event_enqueued", alert_name=alert.alert_name)
    except Exception as exc:
        log.error("k8s_ingest_callback_error", error=str(exc))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    log.info("runbookiq_starting", env=settings.app_env)

    import os
    os.makedirs(settings.upload_dir, exist_ok=True)

    # Auto-start K8s watcher if kubeconfig is configured
    k8s_task = None
    if settings.k8s_kubeconfig:
        from app.ingestion.k8s_connector import start_k8s_watcher
        k8s_task = asyncio.create_task(
            start_k8s_watcher(_k8s_ingest_callback, namespace=settings.k8s_namespace)
        )
        log.info("k8s_watcher_started", kubeconfig=settings.k8s_kubeconfig, namespace=settings.k8s_namespace)

    yield

    log.info("runbookiq_shutting_down")
    if k8s_task:
        k8s_task.cancel()
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
