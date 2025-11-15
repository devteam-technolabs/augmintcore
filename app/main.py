# Mount your routers here and wire everything up.
# FastAPI entrypoint (create_app function)
# Go simple, but think grandly.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import events
from app.core.config import get_settings
from app.db.session import engine

import time
import logging
import inspect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from app.api.router import router as api_router



settings = get_settings()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="augmint_core", debug=settings.DEBUG)

    # CORS
    origins = settings.CORS_ORIGINS or []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    # include API router
    app.include_router(api_router, prefix="/api")

    # Startup and shutdown events
    async def _on_startup() -> None:
        # record start time for runtime reporting
        app.state.start_time = time.time()
        logger.info("Application startup initiated")

        # call optional project-specific startup hook
        if hasattr(events, "startup") and callable(events.startup):
            res = events.startup()
            if inspect.isawaitable(res):
                await res

        # quick DB connectivity check (non-fatal) — support AsyncEngine and sync engines
        try:
            if isinstance(engine, AsyncEngine):
                # async engine
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            else:
                # sync engine
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            logger.info("Database connection OK")
        except Exception as exc:  # keep broad to avoid crashing startup
            logger.exception("Database connectivity check failed: %s", exc)

    async def _on_shutdown() -> None:
        # call optional project-specific shutdown hook
        logger.info("Application shutdown initiated")
        if hasattr(events, "shutdown") and callable(events.shutdown):
            res = events.shutdown()
            if inspect.isawaitable(res):
                await res

        # dispose engine (cleanup) — handle awaitable or non-awaitable dispose()
        try:
            dispose_fn = getattr(engine, "dispose", None)
            if callable(dispose_fn):
                res = dispose_fn()
                if inspect.isawaitable(res):
                    await res
            logger.info("DB engine disposed")
        except Exception as exc:
            logger.exception("Error disposing DB engine: %s", exc)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return app


app = create_app()
