.PHONY: help build up down logs shell migrate new-migration

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