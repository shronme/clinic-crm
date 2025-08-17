from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_services():
    """Get all services."""
    return {"message": "Get services endpoint - to be implemented"}

@router.post("/")
async def create_service():
    """Create new service."""
    return {"message": "Create service endpoint - to be implemented"}

@router.get("/categories")
async def get_service_categories():
    """Get service categories."""
    return {"message": "Get service categories endpoint - to be implemented"}

@router.post("/categories")
async def create_service_category():
    """Create service category."""
    return {"message": "Create service category endpoint - to be implemented"}