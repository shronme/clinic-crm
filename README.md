# Clinic CRM - Barber & Beautician Booking System

A lightweight, multi-tenant CRM and online booking platform for small barber shops and beauty salons.

## Features

- Multi-business, multi-location support
- Staff and service management with per-staff service mapping
- Real-time appointment scheduling with conflict prevention
- Customer profiles and appointment history
- Post-appointment notes with photos and chemical formulas
- Automated notifications via email/SMS
- Admin web app and customer booking portal (PWA)

## Tech Stack

- **Backend**: Python 3.11 + FastAPI
- **Database**: PostgreSQL 15
- **Cache**: Redis 7
- **Task Queue**: Celery
- **Container**: Docker & Docker Compose

## Quick Start

1. **Clone and setup environment**:

   ```bash
   git clone <repository-url>
   cd clinic-crm
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Start with Docker Compose**:

   ```bash
   docker-compose up -d
   ```

3. **Access the application**:
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Celery Flower: http://localhost:5555

## Development Setup

1. **Install Python dependencies**:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Start services**:

   ```bash
   # Start PostgreSQL and Redis
   docker-compose up postgres redis -d

   # Run migrations
   alembic upgrade head

   # Start FastAPI server
   uvicorn app.main:app --reload

   # Start Celery worker (in another terminal)
   celery -A core.celery worker --loglevel=info
   ```

## Project Structure

```
clinic-crm/
├── app/
│   ├── api/v1/endpoints/     # API endpoints
│   ├── core/                 # Core configuration and setup
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic schemas
│   ├── services/             # Business logic
│   └── utils/                # Utility functions
├── alembic/                  # Database migrations
├── uploads/                  # File uploads
├── docker-compose.yml        # Docker services
├── Dockerfile               # API container
└── requirements.txt         # Python dependencies
```

## Development Status

This project is currently in early development. The basic project structure and development environment have been set up (Tasks 1-2 completed).

### Completed Tasks

- ✅ Task 1: Initialize project structure with Python/FastAPI backend
- ✅ Task 2: Set up development environment with Docker containers

### Next Steps

- Task 3: Design and implement database schema
- Task 4: Implement multi-tenant data isolation
- Task 5: Create authentication system

## Contributing

This project follows the specification outlined in `barber_beautician_crm_spec.md`. See the Implementation Task List (Section 21) for detailed development roadmap.

## License

[Add license information]
