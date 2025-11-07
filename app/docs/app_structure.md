<!-- Date: 07/November/2025 -->
augmint_core/
│
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── users.py
│   │   │   │   ├── auth.py
│   │   │   │   ├── healthcheck.py
│   │   │   │   └── ...
│   │   └── router.py
│   │
│   ├── core/                      # Global config, app-level logic
│   │   ├── __init__.py
│   │   ├── config.py              # Settings via pydantic BaseSettings
│   │   ├── security.py
│   │   ├── logging_config.py      # Custom logging configuration
│   │   ├── rate_limiter.py        # Redis rate limiter middleware
│   │   ├── cache.py               # Central cache setup (Redis)
│   │   ├── events.py              # Startup/shutdown events
│   │   └── middlewares.py         # Global middlewares (CORS, error handling)
│   │
│   ├── models/                    # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── post.py
│   │   └── ...
│   │
│   ├── schemas/                   # Pydantic schemas (validation)
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── post.py
│   │
│   ├── crud/                      # DB access logic
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── post.py
│   │
│   ├── db/                        # Database session & base config
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── session.py
│   │   ├── init_db.py             # Seeding initial data
│   │   └── migrations/            # Alembic migrations folder
│   │       ├── env.py
│   │       ├── versions/
│   │       └── README
│   │
│   ├── services/                  # Business logic layer (e.g. email, payments)
│   │   ├── __init__.py
│   │   ├── email_service.py
│   │   ├── notification_service.py
│   │   ├── auth_service.py
│   │   ├── payment_service.py
│   │   └── background_tasks.py
│   │
│   ├── utils/                     # Utility/helper functions
│   │   ├── __init__.py
│   │   ├── datetime_utils.py
│   │   ├── pagination.py
│   │   ├── hashing.py
│   │   └── response_handler.py
│   │
│   ├── main.py                    # FastAPI entrypoint (create_app function)
│   └── asgi.py                    # For ASGI servers like Uvicorn/Gunicorn
│
├── scripts/                       # Helper scripts (seeding, maintenance)
│   ├── create_superuser.py
│   ├── backup_db.py
│   └── ...
│
├── alembic.ini                    # Alembic config
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── test_users.py
│   ├── test_auth.py
│   ├── test_healthcheck.py
│   └── integration/
│
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── entrypoint.sh
│   └── nginx.conf
│
├── .env                           # Environment variables
├── .env.example                   # Template for new devs
├── .gitignore
├── pyproject.toml or requirements.txt
├── README.md
└── Makefile                       # CLI shortcuts (run, lint, test, format)

## Python version Used
python3.13.5