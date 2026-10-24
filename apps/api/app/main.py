"""FastAPI application entry point (`uvicorn app.main:app`)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import config, db
from app.core.config import get_settings
from app.routers import chat, health, plan, rooms, spec
from app.workers.background import lifespan


def create_app() -> FastAPI:
    """Apply migrations, build the FastAPI application and register routers."""
    settings = get_settings()
    db.init()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(rooms.router)
    app.include_router(chat.router)
    app.include_router(spec.router)
    app.include_router(plan.router)
    return app


app = create_app()
