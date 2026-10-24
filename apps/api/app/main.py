"""FastAPI application entry point (`uvicorn app.main:app`)."""

from fastapi import FastAPI

from app.core.config import get_settings
from app.routers import health


def create_app() -> FastAPI:
    """Build the FastAPI application and register routers."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.include_router(health.router)
    return app


app = create_app()
