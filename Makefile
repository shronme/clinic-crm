.PHONY: help build up down logs shell migrate new-migration setup-test-db cleanup-test-db test

# Default target
help:
	@echo "Available commands:"
	@echo "  build          - Build all containers"
	@echo "  up             - Start all services"
	@echo "  down           - Stop all services"
	@echo "  logs           - View logs for all services"
	@echo "  shell          - Open shell in API container"
	@echo "  migrate        - Run database migrations"
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