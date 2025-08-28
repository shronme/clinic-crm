from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    business,
    staff,
    services,
    customers,
    appointments,
    scheduling,
    public,
)

api_router = APIRouter()

# Authentication endpoints
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Business management endpoints
api_router.include_router(business.router, prefix="/business", tags=["business"])

# Staff management endpoints
api_router.include_router(staff.router, prefix="/staff", tags=["staff"])

# Service management endpoints
api_router.include_router(services.router, prefix="/services", tags=["services"])

# Customer management endpoints
api_router.include_router(customers.router, prefix="/customers", tags=["customers"])

# Appointment management endpoints
api_router.include_router(
    appointments.router, prefix="/appointments", tags=["appointments"]
)

# Scheduling endpoints
api_router.include_router(scheduling.router, prefix="/scheduling", tags=["scheduling"])

# Public booking endpoints (customer-facing)
api_router.include_router(public.router, prefix="/public", tags=["public"])
