"""App entrypoint — thin wiring only. Logic lives in services/routers."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import applications, auth, future, health, jobs, resumes
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.db.database import init_db

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level)
    init_db()
    log.info("darkhouse backend ready (db=%s)", "postgres" if s.is_postgres else "sqlite")
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="darkhouse", version="0.2.0", lifespan=lifespan)
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
