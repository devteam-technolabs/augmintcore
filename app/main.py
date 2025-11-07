# Mount your routers here and wire everything up.
# FastAPI entrypoint (create_app function)
# Go simple, but think grandly.

from fastapi import FastAPI
from app.api.v1.endpoints import users, auth

app = FastAPI()

app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])