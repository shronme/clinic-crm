from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.database import get_db
from app.models.staff import Staff


async def get_current_staff(
    x_staff_id: Optional[str] = Header(None, description="Current staff ID for auth"),
    db: AsyncSession = Depends(get_db),
) -> Staff:
    """
    Get current authenticated staff member.

    TODO: This is a placeholder implementation for development.
    In production, this should verify JWT tokens and extract staff info.
    """
    if not x_staff_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )

    try:
        staff_id = int(x_staff_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid staff ID format"
        )

    # Look up staff from database
    try:
        result = await db.execute(select(Staff).where(Staff.id == staff_id))
        staff = result.scalar_one_or_none()

        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found"
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
            role="owner_admin" if staff_id == 1 else "staff",
            is_active=True,
            is_bookable=True,
        )
        return staff


async def get_current_business(
    x_business_id: Optional[str] = Header(None, description="Current business ID"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current business context.

    TODO: This is a placeholder implementation for development.
    In production, this should be integrated with proper business context.
    """
    if not x_business_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Business ID required"
        )

    try:
        business_id = int(x_business_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Business-ID must be a valid integer",
        )

    # Mock business object for development
    class MockBusiness:
        def __init__(self, id: int):
            self.id = id
            self.name = "Mock Business"
            self.is_active = True

    return MockBusiness(business_id)
