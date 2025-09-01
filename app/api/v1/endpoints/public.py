from fastapi import APIRouter

router = APIRouter()


@router.post("/availability/search")
async def search_availability():
    """Search available time slots for booking."""
    return {"message": "Search availability endpoint - to be implemented"}


@router.post("/appointments")
async def create_public_appointment():
    """Create appointment (customer-facing)."""
    return {"message": "Create public appointment endpoint - to be implemented"}


@router.post("/appointments/{appointment_id}/confirm")
async def confirm_appointment():
    """Confirm tentative appointment."""
    return {"message": "Confirm appointment endpoint - to be implemented"}


@router.post("/appointments/{appointment_id}/reschedule")
async def reschedule_appointment():
    """Reschedule appointment."""
    return {"message": "Reschedule appointment endpoint - to be implemented"}


@router.post("/appointments/{appointment_id}/cancel")
async def cancel_appointment():
    """Cancel appointment."""
    return {"message": "Cancel appointment endpoint - to be implemented"}
