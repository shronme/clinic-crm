from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.database import get_db
from app.services.business import business_service
from app.schemas.business import BusinessCreate, BusinessUpdate, BusinessResponse

router = APIRouter()


@router.post("/", response_model=BusinessResponse, status_code=status.HTTP_201_CREATED)
async def create_business(
    business_data: BusinessCreate, db: AsyncSession = Depends(get_db)
):
    """Create a new business."""
    try:
        business = await business_service.create_business(db, business_data)
        return business
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create business",
        )


@router.get("/{business_uuid}", response_model=BusinessResponse)
async def get_business(business_uuid: UUID, db: AsyncSession = Depends(get_db)):
    """Get business profile by UUID."""
    business = await business_service.get_business_by_uuid(db, business_uuid)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business not found"
        )
    return business


@router.get("/", response_model=List[BusinessResponse])
async def get_businesses(
    skip: int = Query(0, ge=0, description="Number of businesses to skip"),
    limit: int = Query(
        100, ge=1, le=1000, description="Number of businesses to return"
    ),
    active_only: bool = Query(True, description="Return only active businesses"),
    db: AsyncSession = Depends(get_db),
):
    """Get list of businesses with pagination."""
    businesses = await business_service.get_businesses(
        db, skip=skip, limit=limit, active_only=active_only
    )
    return businesses


@router.put("/{business_uuid}", response_model=BusinessResponse)
async def update_business(
    business_uuid: UUID,
    business_update: BusinessUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update business profile."""
    try:
        business = await business_service.update_business_by_uuid(
            db, business_uuid, business_update
        )
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Business not found"
            )
        return business
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update business",
        )


@router.delete("/{business_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_business(
    business_uuid: UUID,
    hard_delete: bool = Query(
        False, description="Perform hard delete instead of soft delete"
    ),
    db: AsyncSession = Depends(get_db),
):
    """Delete business (soft delete by default)."""
    success = await business_service.delete_business_by_uuid(
        db, business_uuid, soft_delete=not hard_delete
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business not found"
        )


@router.post("/{business_uuid}/activate", response_model=BusinessResponse)
async def activate_business(business_uuid: UUID, db: AsyncSession = Depends(get_db)):
    """Reactivate a soft-deleted business."""
    business = await business_service.activate_business_by_uuid(db, business_uuid)
    if not business:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Business not found"
        )
    return business
