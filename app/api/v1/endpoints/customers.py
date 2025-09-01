from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.api.deps.database import get_db
from app.api.deps.business import get_business_from_header
from app.models.business import Business
from app.models.customer import CustomerStatus
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerListResponse,
    CustomerSearch,
    CustomerStats,
    CustomerCSVImport,
    CustomerCSVImportResponse,
)
from app.services.customer import customer_service

router = APIRouter()


@router.post("/", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_business_from_header),
):
    """Create a new customer."""
    try:
        customer = await customer_service.create_customer(
            db, customer_data, business.id
        )
        return CustomerResponse.from_orm(customer)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=CustomerListResponse)
async def get_customers(
    skip: int = Query(0, ge=0, description="Number of customers to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of customers to return"),
    status: Optional[CustomerStatus] = Query(
        None, description="Filter by customer status"
    ),
    include_inactive: bool = Query(False, description="Include inactive customers"),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_business_from_header),
):
    """Get list of customers with pagination."""
    try:
        customers = await customer_service.get_customers(
            db=db,
            business_id=business.id,
            skip=skip,
            limit=limit,
            status_filter=status,
            include_inactive=include_inactive,
        )

        # For now, return simple list. In production, you'd want total count for pagination
        return CustomerListResponse(
            customers=[CustomerResponse.from_orm(customer) for customer in customers],
            total=len(customers),  # This should be actual total count from database
            page=skip // limit + 1,
            page_size=limit,
            total_pages=((len(customers) - 1) // limit + 1) if customers else 0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve customers")


@router.post("/search", response_model=CustomerListResponse)
async def search_customers(
    search_params: CustomerSearch,
    skip: int = Query(0, ge=0, description="Number of customers to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of customers to return"),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_business_from_header),
):
    """Search customers with advanced filtering."""
    try:
        customers, total = await customer_service.search_customers(
            db=db,
            business_id=business.id,
            search_params=search_params,
            skip=skip,
            limit=limit,
        )

        return CustomerListResponse(
            customers=[CustomerResponse.from_orm(customer) for customer in customers],
            total=total,
            page=skip // limit + 1,
            page_size=limit,
            total_pages=((total - 1) // limit + 1) if total > 0 else 0,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to search customers")


@router.get("/stats", response_model=CustomerStats)
async def get_customer_stats(
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_business_from_header),
):
    """Get customer statistics for the business."""
    try:
        stats = await customer_service.get_customer_stats(db, business.id)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve customer statistics"
        )


@router.get("/{customer_uuid}", response_model=CustomerResponse)
async def get_customer(
    customer_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_business_from_header),
):
    """Get specific customer by UUID."""
    try:
        customer = await customer_service.get_customer_by_uuid(
            db, customer_uuid, business.id
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return CustomerResponse.from_orm(customer)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve customer")


@router.put("/{customer_uuid}", response_model=CustomerResponse)
async def update_customer(
    customer_uuid: UUID,
    customer_update: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_business_from_header),
):
    """Update customer information."""
    try:
        customer = await customer_service.update_customer(
            db, customer_uuid, customer_update, business.id
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")
        return CustomerResponse.from_orm(customer)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to update customer")


@router.delete("/{customer_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_uuid: UUID,
    soft_delete: bool = Query(
        True, description="Perform soft delete (deactivate) instead of hard delete"
    ),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_business_from_header),
):
    """Delete or deactivate customer."""
    try:
        deleted = await customer_service.delete_customer(
            db, customer_uuid, business.id, soft_delete
        )
        if not deleted:
            raise HTTPException(status_code=404, detail="Customer not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to delete customer")


@router.get("/{customer_uuid}/appointments")
async def get_customer_appointment_history(
    customer_uuid: UUID,
    limit: int = Query(
        50, ge=1, le=200, description="Number of appointments to return"
    ),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_business_from_header),
):
    """Get customer's appointment history."""
    try:
        appointments = await customer_service.get_customer_appointment_history(
            db, customer_uuid, business.id, limit
        )
        # Return simplified appointment data or use proper appointment response schema
        return {"appointments": appointments}  # In production, use proper schema
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve appointment history"
        )


@router.post("/import", response_model=CustomerCSVImportResponse)
async def import_customers_from_csv(
    import_data: CustomerCSVImport,
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_business_from_header),
):
    """Import customers from CSV file."""
    try:
        result = await customer_service.import_customers_from_csv(
            db, business.id, import_data
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to import customers: {str(e)}"
        )


@router.post("/{customer_uuid}/visit")
async def update_customer_visit_stats(
    customer_uuid: UUID,
    amount_spent: float = Query(0.0, ge=0, description="Amount spent in dollars"),
    db: AsyncSession = Depends(get_db),
    business: Business = Depends(get_business_from_header),
):
    """Update customer visit statistics after an appointment."""
    try:
        customer = await customer_service.get_customer_by_uuid(
            db, customer_uuid, business.id
        )
        if not customer:
            raise HTTPException(status_code=404, detail="Customer not found")

        amount_cents = int(amount_spent * 100)
        await customer_service.update_customer_visit_stats(
            db, customer.id, amount_spent=amount_cents
        )

        return {"message": "Customer visit stats updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Failed to update customer visit stats"
        )
