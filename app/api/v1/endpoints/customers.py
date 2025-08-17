from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_customers():
    """Get all customers."""
    return {"message": "Get customers endpoint - to be implemented"}

@router.post("/")
async def create_customer():
    """Create new customer."""
    return {"message": "Create customer endpoint - to be implemented"}

@router.get("/{customer_id}")
async def get_customer():
    """Get specific customer."""
    return {"message": "Get customer endpoint - to be implemented"}

@router.post("/import")
async def import_customers():
    """Import customers from CSV."""
    return {"message": "Import customers endpoint - to be implemented"}