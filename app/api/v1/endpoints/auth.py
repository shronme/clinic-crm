from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.database import get_db
from app.services.auth import AuthService
from app.schemas.staff import StaffResponse, StaffMeResponse
from app.services.business import business_service
from app.schemas.business import BusinessResponse

router = APIRouter()
security = HTTPBearer()


@router.get("/me", response_model=StaffMeResponse)
async def get_current_user_info(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """Get current authenticated user information. Auto-setup if user doesn't exist."""
    token = credentials.credentials

    # Validate Descope token and extract user info
    user_info = await AuthService.validate_descope_token(token)
    descope_user_id = user_info["descope_user_id"]

    # Try to get existing staff member
    staff = await AuthService.get_user_by_descope_id(descope_user_id, db)

    if not staff:
        # Staff doesn't exist, auto-setup
        staff = await AuthService.get_or_create_user_from_descope(
            descope_user_id=descope_user_id,
            email=user_info["email"],
            name=user_info["name"],
            db=db,
        )

    # Load business details
    business = await business_service.get_business(db, staff.business_id)

    staff_payload = StaffResponse.from_staff(staff)
    business_payload = BusinessResponse.model_validate(business)
    return StaffMeResponse(**staff_payload.dict(), business=business_payload)


@router.post("/setup", response_model=StaffResponse)
async def setup_new_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    """
    Setup new user account after Descope signup.
    Creates business and staff record with OWNER_ADMIN role.
    """
    token = credentials.credentials

    # Validate Descope token and extract user info
    user_info = await AuthService.validate_descope_token(token)

    # Get or create user
    staff = await AuthService.get_or_create_user_from_descope(
        descope_user_id=user_info["descope_user_id"],
        email=user_info["email"],
        name=user_info["name"],
        db=db,
    )

    return StaffResponse.from_staff(staff)


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
