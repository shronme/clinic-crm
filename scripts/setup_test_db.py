#!/usr/bin/env python3
"""
Script to set up the test PostgreSQL database for running tests.
This creates a fresh test database and ensures it's ready for testing.
"""

import asyncio
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine
from app.core.database import Base

# Test database configuration
TEST_DB_NAME = "test_clinic_crm"

# Detect if we're running inside Docker container
import os

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
MASTER_DB_NAME = "clinic_crm"

TEST_DB_URL = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:"
    f"{DB_PORT}/{TEST_DB_NAME}"
)
MASTER_DB_URL = (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:"
    f"{DB_PORT}/{MASTER_DB_NAME}"
)


async def setup_test_database():
    """Set up the test database."""
    print(f"Setting up test database: {TEST_DB_NAME}")

    try:
        # Connect to master database to create/drop test database
        master_conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=MASTER_DB_NAME,
        )

        # Drop test database if it exists
        await master_conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        print(f"Dropped existing database: {TEST_DB_NAME}")

        # Create fresh test database
        await master_conn.execute(f"CREATE DATABASE {TEST_DB_NAME}")
        print(f"Created new database: {TEST_DB_NAME}")

        await master_conn.close()

        # Connect to test database and create tables
        engine = create_async_engine(TEST_DB_URL, echo=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("Created all database tables")
        await engine.dispose()

        print("✅ Test database setup complete!")
        print(f"Database URL: {TEST_DB_URL}")

    except Exception as e:
        print(f"❌ Error setting up test database: {e}")
        print("\nMake sure PostgreSQL is running and accessible with:")
        print(f"  - Host: {DB_HOST}")
        print(f"  - Port: {DB_PORT}")
        print(f"  - User: {DB_USER}")
        print(f"  - Password: {DB_PASSWORD}")
        print(f"  - Database: {MASTER_DB_NAME}")
        print("\nYou can start PostgreSQL with:")
        print("  docker-compose up -d db")
        return False

    return True


async def cleanup_test_database():
    """Clean up the test database."""
    print(f"Cleaning up test database: {TEST_DB_NAME}")

    try:
        master_conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=MASTER_DB_NAME,
        )

        await master_conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}")
        print(f"✅ Dropped test database: {TEST_DB_NAME}")

        await master_conn.close()

    except Exception as e:
        print(f"❌ Error cleaning up test database: {e}")
        return False

    return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        asyncio.run(cleanup_test_database())
    else:
        asyncio.run(setup_test_database())
