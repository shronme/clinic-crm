
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.api.deps.database import get_db
from app.core.config import settings
from app.models.staff import Staff

# Import Descope only if available
try:
    from descope import AuthException, DescopeClient
    DESCOPE_AVAILABLE = True
except ImportError:
    AuthException = Exception  # Fallback for type hints
    DescopeClient = None
    DESCOPE_AVAILABLE = False

logger = structlog.get_logger(__name__)


# Initialize Descope client (only if configured and available)
descope_client = None
if DESCOPE_AVAILABLE and settings.DESCOPE_PROJECT_ID:
    descope_client = DescopeClient(
        project_id=settings.DESCOPE_PROJECT_ID,
        management_key=settings.DESCOPE_MANAGEMENT_KEY,
    )

# HTTP Bearer token extractor
security = HTTPBearer()


async def get_current_staff(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Staff:
    """
    Get current authenticated staff member.
    
    - In production: Validates Descope JWT token and extracts staff info
    - In test/dev: Falls back to header-based auth if Descope not configured
    """
    
    # If Descope is not configured (tests/dev), fall back to old header auth
    if not descope_client:
        logger.warning("Descope not configured, using development auth fallback")
        return await _get_staff_dev_fallback(credentials.credentials, db)
    
    token = credentials.credentials
    
    try:
        # Validate JWT token with Descope
        jwt_response = descope_client.validate_session(token)
        
        if not jwt_response.valid:
            logger.warning("Invalid JWT token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token"
            )
        
        # Extract user information from JWT
        user_info = jwt_response.claims
        descope_user_id = user_info.get("sub")  # Subject (user ID)
        email = user_info.get("email")
        
        # Extract custom claims (business_id, staff_id, role)
        custom_attrs = user_info.get("customAttributes", {})
        staff_id = custom_attrs.get("staff_id")
        business_id = custom_attrs.get("business_id")
        
        if not staff_id:
            logger.error(
                "Staff ID not found in JWT token", 
                descope_user_id=descope_user_id,
                email=email
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff information not found in token"
            )
        
        # Look up staff from database
        result = await db.execute(
            select(Staff).where(Staff.id == int(staff_id))
        )
        staff = result.scalar_one_or_none()
        
        if not staff:
            logger.error(
                "Staff not found in database",
                staff_id=staff_id,
                descope_user_id=descope_user_id
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Staff member not found"
            )
        
        if not staff.is_active:
            logger.warning(
                "Inactive staff attempted access",
                staff_id=staff_id,
                business_id=staff.business_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff account is inactive"
            )
        
        # Verify business_id matches (security check)
        if business_id and staff.business_id != int(business_id):
            logger.error(
                "Business ID mismatch",
                token_business_id=business_id,
                staff_business_id=staff.business_id,
                staff_id=staff_id
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Business access mismatch"
            )
        
        logger.info(
            "Staff authenticated successfully",
            staff_id=staff.id,
            staff_name=staff.name,
            business_id=staff.business_id,
            role=staff.role
        )
        
        return staff
        
    except AuthException as e:
        logger.error("Descope authentication error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected authentication error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


async def _get_staff_dev_fallback(token: str, db: AsyncSession) -> Staff:
    """
    Development/test fallback authentication.
    Expects token to be a simple staff ID string.
    """
    try:
        staff_id = int(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid staff ID format"
        )

    # Look up staff from database
    try:
        result = await db.execute(select(Staff).where(Staff.id == staff_id))
        staff = result.scalar_one_or_none()

        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Staff member not found"
            )

        if not staff.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Staff account is inactive",
            )

        return staff

    except HTTPException:
        raise
    except Exception:
        # Fallback to mock staff for development if database lookup fails
        staff = Staff(
            id=staff_id,
            business_id=1,
            name="Mock Staff",
            email="mock@test.com",
            role="OWNER_ADMIN" if staff_id == 1 else "STAFF",
            is_active=True,
            is_bookable=True,
        )
        return staff
