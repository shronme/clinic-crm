# ✅ COMPLETED: SQLAlchemy async imports and dependencies
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ✅ COMPLETED: Async database engine configuration
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # Disabled to prevent SQLAlchemy engine logs
    future=True,
    pool_pre_ping=True,
    pool_recycle=300,
)

# ✅ COMPLETED: Async session factory setup
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# ✅ COMPLETED: SQLAlchemy Base class for models
Base = declarative_base()


# ✅ COMPLETED: Database initialization function for connection setup
async def init_db():
    """Initialize database connection and import models."""
    try:
        # Test database connection
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))

        logger.info("Database connection initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", exc_info=e)
        raise


# ✅ COMPLETED: Database session dependency with error handling and cleanup
async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error("Database session error", exc_info=e)
            raise
        finally:
            await session.close()
