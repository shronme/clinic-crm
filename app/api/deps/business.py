from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.database import get_db
from app.models.business import Business
from app.services.business import business_service

logger = structlog.get_logger(__name__)

class BusinessContext:
    """Business context for multi-tenant operations."""
    
    def __init__(self, business: Business):
        self.business = business
        self.business_id = business.id
        self.timezone = business.timezone
        self.currency = business.currency
        self.is_active = business.is_active

async def get_business_context(
    business_id: int,
    db: AsyncSession = Depends(get_db)
) -> BusinessContext:
    """
    Get business context for multi-tenant operations.
    
    This dependency ensures that:
    1. The business exists
    2. The business is active
    3. All subsequent operations are scoped to this business
    """
    try:
        business = await business_service.get_business(db, business_id)
        
        if not business:
            logger.warning("Business not found for context", business_id=business_id)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business not found"
            )
        
        if not business.is_active:
            logger.warning("Inactive business access attempted", business_id=business_id)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Business is inactive"
            )
        
        logger.info("Business context established", business_id=business_id, business_name=business.name)
        return BusinessContext(business)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to establish business context", business_id=business_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to establish business context"
        )

async def get_business_from_header(
    x_business_id: Optional[str] = Header(None, description="Business ID for multi-tenant operations"),
    db: AsyncSession = Depends(get_db)
) -> BusinessContext:
    """
    Get business context from header for API operations.
    
    This dependency is useful for:
    1. API endpoints that need business context from headers
    2. Multi-tenant operations where business_id is not in the URL
    """
    if not x_business_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Business-ID header is required"
        )
    
    try:
        business_id = int(x_business_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Business-ID must be a valid integer"
        )
    
    return await get_business_context(business_id, db)

def require_business_owner():
    """
    Dependency factory for business owner permissions.
    
    TODO: Implement after authentication system is in place.
    This should check that the current user is the owner/admin of the business.
    """
    async def _check_business_owner(
        business_context: BusinessContext = Depends(get_business_context)
    ):
        # Placeholder for owner permission check
        # Will be implemented when auth system is ready
        return business_context
    
    return _check_business_owner

def require_business_staff():
    """
    Dependency factory for business staff permissions.
    
    TODO: Implement after authentication system is in place.
    This should check that the current user is staff/owner/admin of the business.
    """
    async def _check_business_staff(
        business_context: BusinessContext = Depends(get_business_context)
    ):
        # Placeholder for staff permission check
        # Will be implemented when auth system is ready
        return business_context
    
    return _check_business_staff