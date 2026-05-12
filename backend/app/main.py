"""FastAPI entrypoint. Wires middleware, exception handlers, and the v1 router."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import asyncio

from app import __version__
from app.api.v1 import api_router as api_v1_router
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.logging import configure_logging, get_logger
from app.core.problem_details import install_exception_handlers
from app.services.obsidian.queue import queue_loop as obsidian_queue_loop
from app.services.obsidian.watcher import watch_loop as obsidian_watch_loop
from app.services.scheduler import daily_snapshot_loop


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    log = get_logger("app.lifespan")
    settings = get_settings()
    log.info("startup", version=__version__, env=settings.app_env)
    bg_tasks: list[asyncio.Task] = []
    if settings.enable_scheduler and settings.app_env != "test":
        bg_tasks.append(asyncio.create_task(daily_snapshot_loop(), name="daily-snapshot"))
        bg_tasks.append(asyncio.create_task(obsidian_queue_loop(), name="obsidian-queue"))
        # The watcher exits immediately if Obsidian is disabled or sync_mode
        # is not 'two_way' — costless when not used.
        bg_tasks.append(asyncio.create_task(obsidian_watch_loop(), name="obsidian-watcher"))
        log.info("background_workers_started", n=len(bg_tasks))
    try:
        yield
    finally:
        for t in bg_tasks:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        await dispose_engine()
        log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="SportEdge Pro API",
        version=__version__,
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
        docs_url=f"{settings.api_v1_prefix}/docs",
        redoc_url=f"{settings.api_v1_prefix}/redoc",
        lifespan=lifespan,
    )

    # CORS — permissive in dev, locked down behind the reverse proxy in prod.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.app_env == "dev" else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)
    install_exception_handlers(app)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        log = get_logger("app.error")
        log.error("unhandled_exception", error=str(exc), error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "type": "about:blank",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred.",
            },
            media_type="application/problem+json",
        )

    return app


app = create_app()
