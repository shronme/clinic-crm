.PHONY: help build up down logs shell migrate migrate-local migrate-supabase migrate-supabase-file new-migration setup-test-db cleanup-test-db test

# Default target
help:
	@echo "Available commands:"
	@echo "  build          - Build all containers"
	@echo "  up             - Start all services"
	@echo "  down           - Stop all services"
	@echo "  logs           - View logs for all services"
	@echo "  shell          - Open shell in API container"
	@echo "  migrate        - Run database migrations (uses default compose env)"
	@echo "  migrate-local  - Run migrations against local Postgres (no secrets in Makefile)"
	@echo "  migrate-supabase - Run migrations using DATABASE_URL from your shell env"
	@echo "  migrate-supabase-file - Run migrations loading env vars from supabase.env"
	@echo "  new-migration  - Create a new migration (use MSG='description')"
	@echo ""
	@echo "Testing commands:"
	@echo "  setup-test-db  - Set up test PostgreSQL database"
	@echo "  cleanup-test-db- Clean up test database"
	@echo "  test           - Run tests with automatic DB setup/cleanup"

# Docker commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

shell:
	docker-compose exec api bash

# Database migration commands
migrate:
	docker-compose run --rm -v $(PWD):/host -w /host api alembic upgrade head

# Explicit local migration target (no secrets baked in). Uses the compose service hostname
# and default credentials from docker-compose.yml.
migrate-local:
	docker-compose run --rm -v $(PWD):/host -w /host -e DATABASE_URL=postgresql+asyncpg://clinic_user:clinic_password@postgres:5432/clinic_crm api alembic upgrade head

# Supabase migration using DATABASE_URL provided from your shell environment.
# Usage:
#   DATABASE_URL='postgresql+asyncpg://USER:PASS@HOST:5432/DB?sslmode=require' make migrate-supabase
migrate-supabase:
	@if [ -z "$$DATABASE_URL" ]; then \
		echo "Error: DATABASE_URL is not set in your shell environment."; \
		echo "Set it temporarily like:"; \
		echo "  DATABASE_URL='postgresql+asyncpg://USER:PASS@HOST:5432/DB?sslmode=require' make migrate-supabase"; \
		exit 1; \
	fi
	docker-compose run --rm -v $(PWD):/host -w /host -e DATABASE_URL api alembic upgrade head

# Supabase migration loading from a local env file kept out of git.
# Create a file named 'supabase.env' in this folder containing at least:
#   DATABASE_URL=postgresql+asyncpg://USER:PASS@HOST:5432/DB?sslmode=require
# Then run:
#   make migrate-supabase-file
migrate-supabase-file:
	@if [ ! -f supabase.env ]; then \
		echo "Error: supabase.env not found. Create it with DATABASE_URL and keep it out of git."; \
		echo "Example line:"; \
		echo "  DATABASE_URL=postgresql+asyncpg://USER:PASS@HOST:5432/DB?sslmode=require"; \
		exit 1; \
	fi
	docker-compose --env-file supabase.env run --rm -v $(PWD):/host -w /host -e DATABASE_URL api alembic upgrade head

new-migration:
	@if [ -z "$(MSG)" ]; then \
		echo "Error: Please provide a migration message using MSG='your message'"; \
		echo "Example: make new-migration MSG='add user table'"; \
		exit 1; \
	fi
	docker-compose run --rm -v $(PWD):/host -w /host api alembic revision --autogenerate -m "$(MSG)"

# Test database commands
setup-test-db:
	@echo "Setting up test database..."
	docker-compose run --rm -v $(PWD):/host -w /host api python scripts/setup_test_db.py

cleanup-test-db:
	@echo "Cleaning up test database..."
	docker-compose run --rm -v $(PWD):/host -w /host api python scripts/setup_test_db.py cleanup

# Test commands
test: setup-test-db
	@echo "Running tests..."
	docker-compose run --rm -v $(PWD):/host -w /host api pytest tests/ -v
	@echo "Cleaning up test database..."
	docker-compose run --rm -v $(PWD):/host -w /host api python scripts/setup_test_db.py cleanup