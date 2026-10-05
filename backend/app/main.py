"""App entrypoint — thin wiring only. Logic lives in services/routers."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import applications, auth, future, health, jobs, resumes
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.database import init_db

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level)
    s.ensure_production_ready()  # raises -> server refuses to start
    init_db()
    log.info("thedaaakhouse backend ready (db=%s)", "postgres" if s.is_postgres else "sqlite")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="thedaaakhouse", version="0.2.0", lifespan=lifespan)

    @app.exception_handler(Exception)
    async def unhandled(request, exc: Exception):  # noqa: ARG001
        # Full traceback goes to server logs only; clients get a safe message.
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Check the backend logs."},
        )

    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            resp = await call_next(request)
            resp.headers["X-Content-Type-Options"] = "nosniff"
            resp.headers["X-Frame-Options"] = "DENY"
            resp.headers["Referrer-Policy"] = "same-origin"
            resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            return resp

    app.add_middleware(SecurityHeadersMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(resumes.router)
    app.include_router(jobs.router)
    app.include_router(applications.router)
    app.include_router(future.router)
    return app


app = create_app()
