from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from app.config import settings

# Async engine — для приложения
async_url = settings.database_url  # postgresql+asyncpg://...
engine = create_async_engine(async_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Sync engine — для Alembic
sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
sync_engine = create_engine(sync_url, echo=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session