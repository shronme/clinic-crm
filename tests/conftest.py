import asyncio
import os
import sys
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.database import Base, get_db
from app.main import app

# Detect if we're running inside Docker container
if os.path.exists("/.dockerenv"):
    # Inside container - use service names
    DB_HOST = "postgres"
    DB_PORT = 5432
else:
    # Local environment - use localhost
    DB_HOST = "localhost"
    DB_PORT = 5432

# Database credentials from docker-compose.yml
DB_USER = "clinic_user"
DB_PASSWORD = "clinic_password"

# Use environment variable to determine test database
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/test_clinic_crm",
)


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    yield loop

    if not loop.is_running():
        loop.close()


@pytest.fixture
async def db():
    """Create a fresh database session for each test."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=300,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # Clean slate
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture(autouse=True)
def override_get_db(db: AsyncSession):
    """Override the get_db dependency to use test database."""

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent testing."""
    return datetime(2024, 1, 15, 10, 30, 0)


# Test Authentication Utilities
def get_auth_headers(staff_id: int) -> dict[str, str]:
    """
    Generate authentication headers for tests.
    
    Since Descope is not configured in tests, the Bearer token
    is treated as a simple staff ID string by the fallback auth.
    """
    return {"Authorization": f"Bearer {staff_id}"}


# Import all service fixtures to make them available
pytest_plugins = ["tests.fixtures.service_fixtures"]
