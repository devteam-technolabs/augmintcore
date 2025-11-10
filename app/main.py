# Mount your routers here and wire everything up.
# FastAPI entrypoint (create_app function)
# Go simple, but think grandly.

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core import events
from app.core.config import get_settings
from app.db.session import engine

settings = get_settings()


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
    # app.include_router(api_router, prefix="/api")

    # Startup and shutdown events

    return app


app = create_app()
