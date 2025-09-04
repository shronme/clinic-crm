from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_staff
from app.api.deps.database import get_db
from app.models.staff import Staff
from app.schemas.service import (
    Service,
    ServiceAddon,
    ServiceAddonCreate,
    ServiceAddonUpdate,
    ServiceCategory,
    ServiceCategoryCreate,
    ServiceCategoryUpdate,
    ServiceCreate,
    ServiceUpdate,
    StaffService,
    StaffServiceCreate,
    StaffServiceUpdate,
)
from app.services.service import (
    ServiceAddonService,
    ServiceCategoryService,
    ServiceManagementService,
    StaffServiceMappingService,
)

router = APIRouter()


# Service Category endpoints
@router.get("/categories", response_model=list[ServiceCategory])
async def get_service_categories(
    parent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Get service categories."""
    return await ServiceCategoryService.get_categories(
        db,
        current_staff.business_id,
        parent_id,
    )


@router.post("/categories", response_model=ServiceCategory)
async def create_service_category(
    category_data: ServiceCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Create service category."""
    category_data.business_id = current_staff.business_id
    return await ServiceCategoryService.create_category(db, category_data)


@router.get("/categories/{category_uuid}", response_model=ServiceCategory)
async def get_service_category(
    category_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Get a single service category."""
    category = await ServiceCategoryService.get_category_by_uuid(
        db, category_uuid, current_staff.business_id
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.put("/categories/{category_uuid}", response_model=ServiceCategory)
async def update_service_category(
    category_uuid: UUID,
    category_data: ServiceCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Update service category."""
    category = await ServiceCategoryService.update_category_by_uuid(
        db, category_uuid, current_staff.business_id, category_data
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.delete("/categories/{category_uuid}")
async def delete_service_category(
    category_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Delete service category."""
    if not await ServiceCategoryService.delete_category_by_uuid(
        db, category_uuid, current_staff.business_id
    ):
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted successfully"}


# Service Add-on endpoints (must come before parameterized routes)
@router.get("/addons", response_model=list[ServiceAddon])
async def get_service_addons(
    service_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Get service add-ons."""
    return await ServiceAddonService.get_addons(
        db,
        current_staff.business_id,
        service_id,
    )


@router.post("/addons", response_model=ServiceAddon)
async def create_service_addon(
    addon_data: ServiceAddonCreate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Create service add-on."""
    addon_data.business_id = current_staff.business_id
    return await ServiceAddonService.create_addon(db, addon_data)


@router.get("/addons/{addon_uuid}", response_model=ServiceAddon)
async def get_service_addon(
    addon_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Get a single service add-on."""
    addon = await ServiceAddonService.get_addon_by_uuid(
        db,
        addon_uuid,
        current_staff.business_id,
    )
    if not addon:
        raise HTTPException(status_code=404, detail="Add-on not found")
    return addon


@router.put("/addons/{addon_uuid}", response_model=ServiceAddon)
async def update_service_addon(
    addon_uuid: UUID,
    addon_data: ServiceAddonUpdate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Update service add-on."""
    addon = await ServiceAddonService.update_addon_by_uuid(
        db, addon_uuid, current_staff.business_id, addon_data
    )
    if not addon:
        raise HTTPException(status_code=404, detail="Add-on not found")
    return addon


@router.delete("/addons/{addon_uuid}")
async def delete_service_addon(
    addon_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Delete service add-on."""
    if not await ServiceAddonService.delete_addon_by_uuid(
        db,
        addon_uuid,
        current_staff.business_id,
    ):
        raise HTTPException(status_code=404, detail="Add-on not found")
    return {"message": "Add-on deleted successfully"}


# Staff-Service mapping endpoints (must come before parameterized routes)
@router.get("/staff-services", response_model=list[StaffService])
async def get_staff_services(
    staff_id: Optional[int] = None,
    service_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Get staff-service mappings."""
    return await StaffServiceMappingService.get_staff_services(db, staff_id, service_id)


@router.post("/staff-services", response_model=StaffService)
async def create_staff_service(
    mapping_data: StaffServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Create staff-service mapping."""
    return await StaffServiceMappingService.create_staff_service(db, mapping_data)


@router.get("/staff-services/{staff_service_uuid}", response_model=StaffService)
async def get_staff_service(
    staff_service_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Get a single staff-service mapping."""
    mapping = await StaffServiceMappingService.get_staff_service_by_uuid(
        db, staff_service_uuid
    )
    if not mapping:
        raise HTTPException(status_code=404, detail="Staff-service mapping not found")
    return mapping


@router.put("/staff-services/{staff_service_uuid}", response_model=StaffService)
async def update_staff_service(
    staff_service_uuid: UUID,
    mapping_data: StaffServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Update staff-service mapping."""
    mapping = await StaffServiceMappingService.update_staff_service_by_uuid(
        db, staff_service_uuid, mapping_data
    )
    if not mapping:
        raise HTTPException(status_code=404, detail="Staff-service mapping not found")
    return mapping


@router.delete("/staff-services/{staff_service_uuid}")
async def delete_staff_service(
    staff_service_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Delete staff-service mapping."""
    if not await StaffServiceMappingService.delete_staff_service_by_uuid(
        db, staff_service_uuid
    ):
        raise HTTPException(status_code=404, detail="Staff-service mapping not found")
    return {"message": "Staff-service mapping deleted successfully"}


# Service endpoints (parameterized routes must come after specific routes)
@router.get("/", response_model=list[Service])
async def get_services(
    category_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Get all services."""
    return await ServiceManagementService.get_services(
        db, current_staff.business_id, category_id, is_active
    )


@router.post("/", response_model=Service)
async def create_service(
    service_data: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Create new service."""
    service_data.business_id = current_staff.business_id
    return await ServiceManagementService.create_service(db, service_data)


@router.get("/{service_uuid}", response_model=Service)
async def get_service(
    service_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Get a single service."""
    service = await ServiceManagementService.get_service_by_uuid(
        db, service_uuid, current_staff.business_id
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.put("/{service_uuid}", response_model=Service)
async def update_service(
    service_uuid: UUID,
    service_data: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Update service."""
    service = await ServiceManagementService.update_service_by_uuid(
        db, service_uuid, current_staff.business_id, service_data
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.delete("/{service_uuid}")
async def delete_service(
    service_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Delete service."""
    if not await ServiceManagementService.delete_service_by_uuid(
        db, service_uuid, current_staff.business_id
    ):
        raise HTTPException(status_code=404, detail="Service not found")
    return {"message": "Service deleted successfully"}
