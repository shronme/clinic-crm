from fastapi import APIRouter
from uuid import UUID

router = APIRouter()


@router.get("/")
async def get_customers():
    """Get all customers."""
    return {"message": "Get customers endpoint - to be implemented"}


@router.post("/")
async def create_customer():
    """Create new customer."""
    return {"message": "Create customer endpoint - to be implemented"}


@router.get("/{customer_uuid}")
async def get_customer(customer_uuid: UUID):
    """Get specific customer."""
    return {
        "message": "Get customer endpoint - to be implemented",
        "customer_uuid": customer_uuid,
    }


@router.post("/import")
async def import_customers():
    """Import customers from CSV."""
    return {"message": "Import customers endpoint - to be implemented"}
