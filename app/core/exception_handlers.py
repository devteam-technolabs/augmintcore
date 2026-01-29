from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.authentication import AuthenticationError


# Handles FastAPI's authentication errors (401, 403)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    # If FastAPI raised 401 or 403 → override message
    if exc.status_code in (401, 400, 403, 404):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error_message": exc.detail or "Not authenticated"},
        )

    # All other errors → default structure
    return JSONResponse(
        status_code=exc.status_code, content={"error_message": exc.detail}
    )


# Handles Starlette's authentication middleware errors
async def auth_middleware_exception_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(status_code=403, content={"error_message": "Not authenticated"})
