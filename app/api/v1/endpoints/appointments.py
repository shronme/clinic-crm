from fastapi import APIRouter
from uuid import UUID

router = APIRouter()


@router.get("/")
async def get_appointments():
    """Get appointments with filters."""
    return {"message": "Get appointments endpoint - to be implemented"}


@router.post("/")
async def create_appointment():
    """Create new appointment (admin)."""
    return {"message": "Create appointment endpoint - to be implemented"}


@router.get("/{appointment_uuid}")
async def get_appointment(appointment_uuid: UUID):
    """Get specific appointment."""
    return {
        "message": "Get appointment endpoint - to be implemented",
        "appointment_uuid": appointment_uuid
    }


@router.put("/{appointment_uuid}")
async def update_appointment(appointment_uuid: UUID):
    """Update appointment."""
    return {
        "message": "Update appointment endpoint - to be implemented",
        "appointment_uuid": appointment_uuid
    }