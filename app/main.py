# Mount your routers here and wire everything up.
# FastAPI entrypoint (create_app function)
# Go simple, but think grandly.

import asyncio
import inspect
import logging
import os
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.authentication import AuthenticationError

from app.api.coingecko_router import router as coingecko_router
from app.api.exchange_routers import router as exchange_routers
from app.api.payment_routes import router as payment_router
from app.api.router import router as api_router
from app.api.settings_routers import settings_router
from app.api.websocket_routers import coinbase_ws_listener
from app.api.websocket_routers import router as websocket_router
from app.core import events
from app.core.config import get_settings
from app.core.exception_handlers import (
    auth_middleware_exception_handler,
    custom_http_exception_handler,
)
from app.db.session import engine

settings = get_settings()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="augmint_core", debug=settings.DEBUG)
    # app = FastAPI(title="Crypto WebSocket Backend")

    # CORS
    origins = settings.CORS_ORIGINS or []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )
    # Override FastAPI HTTPException handler
    app.add_exception_handler(HTTPException, custom_http_exception_handler)

    # Override Authentication middleware handler
    app.add_exception_handler(AuthenticationError, auth_middleware_exception_handler)
    # include API router
    app.include_router(api_router, prefix="/api")
    app.include_router(payment_router, prefix="/api")
    app.include_router(exchange_routers, prefix="/api")
    app.include_router(websocket_router, prefix="/api")
    app.include_router(coingecko_router, prefix="/api")
    app.include_router(settings_router, prefix="/api/v1")

    # Startup and shutdown events
    async def _on_startup() -> None:
        # record start time for runtime reporting
        app.state.start_time = time.time()
        logger.info("Application startup initiated")
        logger.warning(" STARTUP EVENT TRIGGERED")

        app.state.coinbase_ws_task = asyncio.create_task(coinbase_ws_listener())
        logger.warning(" COINBASE WS TASK CREATED")

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

    # MEDIA DIRECTORY SETUP
    media_path = os.path.join(os.getcwd(), "media")

    # Create media directory if not exists
    if not os.path.exists(media_path):
        os.makedirs(media_path)
        print("Media directory created at:", media_path)

    # Mount media directory
    app.mount("/media", StaticFiles(directory=media_path), name="media")

    return app


app = create_app()
