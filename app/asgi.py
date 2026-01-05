# For ASGI servers like Uvicorn/Gunicorn

from app.main import app

# run the app using this command
#fastapi dev app/asgi.py(auto reload)
# uvicorn app.asgi:app --host 0.0.0.0 --port 8000(stable server)
# alembic revision --autogenerate -m "add the mfa key"(migration)

# alembic upgrade head(migrate)
