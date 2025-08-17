from fastapi import APIRouter

router = APIRouter()

@router.post("/login")
async def login():
    """Admin user login endpoint."""
    return {"message": "Login endpoint - to be implemented"}

@router.post("/magic-link")
async def magic_link():
    """Customer magic link authentication."""
    return {"message": "Magic link endpoint - to be implemented"}

@router.post("/refresh")
async def refresh_token():
    """Refresh JWT token."""
    return {"message": "Refresh token endpoint - to be implemented"}