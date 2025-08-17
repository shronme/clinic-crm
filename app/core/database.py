# ✅ COMPLETED: SQLAlchemy async imports and dependencies
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import structlog

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ✅ COMPLETED: Async database engine configuration
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_recycle=300,
)

# ✅ COMPLETED: Async session factory setup
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# ✅ COMPLETED: SQLAlchemy Base class for models
Base = declarative_base()

# ✅ COMPLETED: Database initialization function with model imports and table creation
async def init_db():
    """Initialize database tables."""
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they are registered
            from app.models import (
                business, staff, service, customer, 
                appointment, note, notification
            )
            
            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
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