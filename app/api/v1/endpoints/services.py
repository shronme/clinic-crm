from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
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
    business_id: int,
    parent_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get service categories."""
    return await ServiceCategoryService.get_categories(db, business_id, parent_id)


@router.post("/categories", response_model=ServiceCategory)
async def create_service_category(
    category_data: ServiceCategoryCreate, db: AsyncSession = Depends(get_db)
):
    """Create service category."""
    return await ServiceCategoryService.create_category(db, category_data)


@router.get("/categories/{category_uuid}", response_model=ServiceCategory)
async def get_service_category(
    category_uuid: UUID, business_id: int, db: AsyncSession = Depends(get_db)
):
    """Get a single service category."""
    category = await ServiceCategoryService.get_category_by_uuid(
        db, category_uuid, business_id
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.put("/categories/{category_uuid}", response_model=ServiceCategory)
async def update_service_category(
    category_uuid: UUID,
    business_id: int,
    category_data: ServiceCategoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update service category."""
    category = await ServiceCategoryService.update_category_by_uuid(
        db, category_uuid, business_id, category_data
    )
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.delete("/categories/{category_uuid}")
async def delete_service_category(
    category_uuid: UUID, business_id: int, db: AsyncSession = Depends(get_db)
):
    """Delete service category."""
    if not await ServiceCategoryService.delete_category_by_uuid(
        db, category_uuid, business_id
    ):
        raise HTTPException(status_code=404, detail="Category not found")
    return {"message": "Category deleted successfully"}


# Service Add-on endpoints (must come before parameterized routes)
@router.get("/addons", response_model=list[ServiceAddon])
async def get_service_addons(
    business_id: int,
    service_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get service add-ons."""
    return await ServiceAddonService.get_addons(db, business_id, service_id)


@router.post("/addons", response_model=ServiceAddon)
async def create_service_addon(
    addon_data: ServiceAddonCreate, db: AsyncSession = Depends(get_db)
):
    """Create service add-on."""
    return await ServiceAddonService.create_addon(db, addon_data)


@router.get("/addons/{addon_uuid}", response_model=ServiceAddon)
async def get_service_addon(
    addon_uuid: UUID, business_id: int, db: AsyncSession = Depends(get_db)
):
    """Get a single service add-on."""
    addon = await ServiceAddonService.get_addon_by_uuid(db, addon_uuid, business_id)
    if not addon:
        raise HTTPException(status_code=404, detail="Add-on not found")
    return addon


@router.put("/addons/{addon_uuid}", response_model=ServiceAddon)
async def update_service_addon(
    addon_uuid: UUID,
    business_id: int,
    addon_data: ServiceAddonUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update service add-on."""
    addon = await ServiceAddonService.update_addon_by_uuid(
        db, addon_uuid, business_id, addon_data
    )
    if not addon:
        raise HTTPException(status_code=404, detail="Add-on not found")
    return addon


@router.delete("/addons/{addon_uuid}")
async def delete_service_addon(
    addon_uuid: UUID, business_id: int, db: AsyncSession = Depends(get_db)
):
    """Delete service add-on."""
    if not await ServiceAddonService.delete_addon_by_uuid(db, addon_uuid, business_id):
        raise HTTPException(status_code=404, detail="Add-on not found")
    return {"message": "Add-on deleted successfully"}


# Staff-Service mapping endpoints (must come before parameterized routes)
@router.get("/staff-services", response_model=list[StaffService])
async def get_staff_services(
    staff_id: Optional[int] = None,
    service_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get staff-service mappings."""
    return await StaffServiceMappingService.get_staff_services(db, staff_id, service_id)


@router.post("/staff-services", response_model=StaffService)
async def create_staff_service(
    mapping_data: StaffServiceCreate, db: AsyncSession = Depends(get_db)
):
    """Create staff-service mapping."""
    return await StaffServiceMappingService.create_staff_service(db, mapping_data)


@router.get("/staff-services/{staff_service_uuid}", response_model=StaffService)
async def get_staff_service(
    staff_service_uuid: UUID, db: AsyncSession = Depends(get_db)
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
    staff_service_uuid: UUID, db: AsyncSession = Depends(get_db)
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
    business_id: int,
    category_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    """Get all services."""
    return await ServiceManagementService.get_services(
        db, business_id, category_id, is_active
    )


@router.post("/", response_model=Service)
async def create_service(
    service_data: ServiceCreate, db: AsyncSession = Depends(get_db)
):
    """Create new service."""
    return await ServiceManagementService.create_service(db, service_data)


@router.get("/{service_uuid}", response_model=Service)
async def get_service(
    service_uuid: UUID, business_id: int, db: AsyncSession = Depends(get_db)
):
    """Get a single service."""
    service = await ServiceManagementService.get_service_by_uuid(
        db, service_uuid, business_id
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.put("/{service_uuid}", response_model=Service)
async def update_service(
    service_uuid: UUID,
    business_id: int,
    service_data: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update service."""
    service = await ServiceManagementService.update_service_by_uuid(
        db, service_uuid, business_id, service_data
    )
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service


@router.delete("/{service_uuid}")
async def delete_service(
    service_uuid: UUID, business_id: int, db: AsyncSession = Depends(get_db)
):
    """Delete service."""
    if not await ServiceManagementService.delete_service_by_uuid(
        db, service_uuid, business_id
    ):
        raise HTTPException(status_code=404, detail="Service not found")
    return {"message": "Service deleted successfully"}
