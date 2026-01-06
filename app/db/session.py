from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db.db_settings import DBSettings

db_settings = DBSettings()

DATABASE_URL = db_settings.DATABASE_URL or (
    f"postgresql+asyncpg://{db_settings.POSTGRES_USER}:{db_settings.POSTGRES_PASSWORD}"
    f"@{db_settings.POSTGRES_HOST}:{db_settings.POSTGRES_PORT}/{db_settings.POSTGRES_DB}"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
