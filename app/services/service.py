from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.models.service_addon import ServiceAddon
from app.models.service_category import ServiceCategory
from app.models.staff_service import StaffService
from app.schemas.service import (
    ServiceAddonCreate,
    ServiceAddonUpdate,
    ServiceCategoryCreate,
    ServiceCategoryUpdate,
    ServiceCreate,
    ServiceUpdate,
    StaffServiceCreate,
    StaffServiceUpdate,
)


class ServiceCategoryService:
    """Business logic for service categories."""

    @staticmethod
    async def get_categories(
        db: AsyncSession, business_id: int, parent_id: Optional[int] = None
    ) -> list[ServiceCategory]:
        """Get service categories, optionally filtered by parent."""
        stmt = select(ServiceCategory).filter(
            ServiceCategory.business_id == business_id
        )
        if parent_id is not None:
            stmt = stmt.filter(ServiceCategory.parent_id == parent_id)
        else:
            stmt = stmt.filter(ServiceCategory.parent_id.is_(None))
        stmt = stmt.order_by(ServiceCategory.sort_order, ServiceCategory.name)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_category(
        db: AsyncSession, category_id: int, business_id: int
    ) -> Optional[ServiceCategory]:
        """Get a single service category."""
        stmt = select(ServiceCategory).filter(
            and_(
                ServiceCategory.id == category_id,
                ServiceCategory.business_id == business_id,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_category_by_uuid(
        db: AsyncSession, category_uuid: UUID, business_id: int
    ) -> Optional[ServiceCategory]:
        """Get a single service category by UUID."""
        stmt = select(ServiceCategory).filter(
            and_(
                ServiceCategory.uuid == category_uuid,
                ServiceCategory.business_id == business_id,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_category(
        db: AsyncSession, category_data: ServiceCategoryCreate
    ) -> ServiceCategory:
        """Create a new service category."""
        # Validate parent category exists and belongs to same business
        if category_data.parent_id:
            parent = await ServiceCategoryService.get_category(
                db, category_data.parent_id, category_data.business_id
            )
            if not parent:
                raise HTTPException(status_code=400, detail="Parent category not found")

        db_category = ServiceCategory(**category_data.model_dump())
        db.add(db_category)
        await db.commit()
        await db.refresh(db_category)
        return db_category

    @staticmethod
    async def update_category(
        db: AsyncSession,
        category_id: int,
        business_id: int,
        category_data: ServiceCategoryUpdate,
    ) -> Optional[ServiceCategory]:
        """Update a service category."""
        db_category = await ServiceCategoryService.get_category(
            db, category_id, business_id
        )
        if not db_category:
            return None

        # Validate parent category if being updated
        if category_data.parent_id:
            if category_data.parent_id == category_id:
                raise HTTPException(
                    status_code=400, detail="Category cannot be its own parent"
                )
            parent = await ServiceCategoryService.get_category(
                db, category_data.parent_id, business_id
            )
            if not parent:
                raise HTTPException(status_code=400, detail="Parent category not found")

        update_data = category_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_category, field, value)

        await db.commit()
        await db.refresh(db_category)
        return db_category

    @staticmethod
    async def update_category_by_uuid(
        db: AsyncSession,
        category_uuid: UUID,
        business_id: int,
        category_data: ServiceCategoryUpdate,
    ) -> Optional[ServiceCategory]:
        """Update a service category by UUID."""
        db_category = await ServiceCategoryService.get_category_by_uuid(
            db, category_uuid, business_id
        )
        if not db_category:
            return None

        # Validate parent category if being updated
        if category_data.parent_id:
            if category_data.parent_id == db_category.id:
                raise HTTPException(
                    status_code=400, detail="Category cannot be its own parent"
                )
            parent = await ServiceCategoryService.get_category(
                db, category_data.parent_id, business_id
            )
            if not parent:
                raise HTTPException(status_code=400, detail="Parent category not found")

        update_data = category_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_category, field, value)

        await db.commit()
        await db.refresh(db_category)
        return db_category

    @staticmethod
    async def delete_category(
        db: AsyncSession, category_id: int, business_id: int
    ) -> bool:
        """Delete a service category."""
        db_category = await ServiceCategoryService.get_category(
            db, category_id, business_id
        )
        if not db_category:
            return False

        # Check for child categories
        children_stmt = select(ServiceCategory).filter(
            ServiceCategory.parent_id == category_id
        )
        children_result = await db.execute(children_stmt)
        if children_result.first():
            raise HTTPException(
                status_code=400, detail="Cannot delete category with child categories"
            )

        # Check for services using this category
        services_stmt = select(Service).filter(Service.category_id == category_id)
        services_result = await db.execute(services_stmt)
        if services_result.first():
            raise HTTPException(
                status_code=400,
                detail="Cannot delete category with associated services",
            )

        await db.delete(db_category)
        await db.commit()
        return True

    @staticmethod
    async def delete_category_by_uuid(
        db: AsyncSession, category_uuid: UUID, business_id: int
    ) -> bool:
        """Delete a service category by UUID."""
        db_category = await ServiceCategoryService.get_category_by_uuid(
            db, category_uuid, business_id
        )
        if not db_category:
            return False

        # Check for child categories
        children_stmt = select(ServiceCategory).filter(
            ServiceCategory.parent_id == db_category.id
        )
        children_result = await db.execute(children_stmt)
        if children_result.first():
            raise HTTPException(
                status_code=400, detail="Cannot delete category with child categories"
            )

        # Check for services using this category
        services_stmt = select(Service).filter(Service.category_id == db_category.id)
        services_result = await db.execute(services_stmt)
        if services_result.first():
            raise HTTPException(
                status_code=400,
                detail="Cannot delete category with associated services",
            )

        await db.delete(db_category)
        await db.commit()
        return True


class ServiceManagementService:
    """Business logic for services."""

    @staticmethod
    async def get_services(
        db: AsyncSession,
        business_id: int,
        category_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> list[Service]:
        """Get services, optionally filtered by category and status."""
        stmt = select(Service).filter(Service.business_id == business_id)
        if category_id is not None:
            stmt = stmt.filter(Service.category_id == category_id)
        if is_active is not None:
            stmt = stmt.filter(Service.is_active == is_active)
        stmt = stmt.order_by(Service.sort_order, Service.name)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_service(
        db: AsyncSession, service_id: int, business_id: int
    ) -> Optional[Service]:
        """Get a single service."""
        stmt = select(Service).filter(
            and_(Service.id == service_id, Service.business_id == business_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_service_by_uuid(
        db: AsyncSession, service_uuid: UUID, business_id: int
    ) -> Optional[Service]:
        """Get a single service by UUID."""
        stmt = select(Service).filter(
            and_(Service.uuid == service_uuid, Service.business_id == business_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_service(db: AsyncSession, service_data: ServiceCreate) -> Service:
        """Create a new service."""
        # Validate category exists if provided
        if service_data.category_id:
            category = await ServiceCategoryService.get_category(
                db, service_data.category_id, service_data.business_id
            )
            if not category:
                raise HTTPException(status_code=400, detail="Category not found")

        db_service = Service(**service_data.model_dump())
        db.add(db_service)
        await db.commit()
        await db.refresh(db_service)
        return db_service

    @staticmethod
    async def update_service(
        db: AsyncSession, service_id: int, business_id: int, service_data: ServiceUpdate
    ) -> Optional[Service]:
        """Update a service."""
        db_service = await ServiceManagementService.get_service(
            db, service_id, business_id
        )
        if not db_service:
            return None

        # Validate category if being updated
        if service_data.category_id:
            category = await ServiceCategoryService.get_category(
                db, service_data.category_id, business_id
            )
            if not category:
                raise HTTPException(status_code=400, detail="Category not found")

        update_data = service_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_service, field, value)

        await db.commit()
        await db.refresh(db_service)
        return db_service

    @staticmethod
    async def update_service_by_uuid(
        db: AsyncSession,
        service_uuid: UUID,
        business_id: int,
        service_data: ServiceUpdate,
    ) -> Optional[Service]:
        """Update a service by UUID."""
        db_service = await ServiceManagementService.get_service_by_uuid(
            db, service_uuid, business_id
        )
        if not db_service:
            return None

        # Validate category if being updated
        if service_data.category_id:
            category = await ServiceCategoryService.get_category(
                db, service_data.category_id, business_id
            )
            if not category:
                raise HTTPException(status_code=400, detail="Category not found")

        update_data = service_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_service, field, value)

        await db.commit()
        await db.refresh(db_service)
        return db_service

    @staticmethod
    async def delete_service(
        db: AsyncSession, service_id: int, business_id: int
    ) -> bool:
        """Delete a service."""
        db_service = await ServiceManagementService.get_service(
            db, service_id, business_id
        )
        if not db_service:
            return False

        # Check for associated staff services
        staff_services_stmt = select(StaffService).filter(
            StaffService.service_id == service_id
        )
        staff_services_result = await db.execute(staff_services_stmt)
        if staff_services_result.first():
            raise HTTPException(
                status_code=400, detail="Cannot delete service with staff assignments"
            )

        await db.delete(db_service)
        await db.commit()
        return True

    @staticmethod
    async def delete_service_by_uuid(
        db: AsyncSession, service_uuid: UUID, business_id: int
    ) -> bool:
        """Delete a service by UUID."""
        db_service = await ServiceManagementService.get_service_by_uuid(
            db, service_uuid, business_id
        )
        if not db_service:
            return False

        # Check for associated staff services
        staff_services_stmt = select(StaffService).filter(
            StaffService.service_id == db_service.id
        )
        staff_services_result = await db.execute(staff_services_stmt)
        if staff_services_result.first():
            raise HTTPException(
                status_code=400, detail="Cannot delete service with staff assignments"
            )

        await db.delete(db_service)
        await db.commit()
        return True


class ServiceAddonService:
    """Business logic for service add-ons."""

    @staticmethod
    async def get_addons(
        db: AsyncSession, business_id: int, service_id: Optional[int] = None
    ) -> list[ServiceAddon]:
        """Get service add-ons, optionally filtered by service."""
        stmt = select(ServiceAddon).filter(ServiceAddon.business_id == business_id)
        if service_id is not None:
            stmt = stmt.filter(ServiceAddon.service_id == service_id)
        stmt = stmt.order_by(ServiceAddon.sort_order, ServiceAddon.name)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_addon(
        db: AsyncSession, addon_id: int, business_id: int
    ) -> Optional[ServiceAddon]:
        """Get a single service add-on."""
        stmt = select(ServiceAddon).filter(
            and_(ServiceAddon.id == addon_id, ServiceAddon.business_id == business_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_addon_by_uuid(
        db: AsyncSession, addon_uuid: UUID, business_id: int
    ) -> Optional[ServiceAddon]:
        """Get a single service add-on by UUID."""
        stmt = select(ServiceAddon).filter(
            and_(
                ServiceAddon.uuid == addon_uuid, ServiceAddon.business_id == business_id
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_addon(
        db: AsyncSession, addon_data: ServiceAddonCreate
    ) -> ServiceAddon:
        """Create a new service add-on."""
        # Validate service exists
        service = await ServiceManagementService.get_service(
            db, addon_data.service_id, addon_data.business_id
        )
        if not service:
            raise HTTPException(status_code=400, detail="Service not found")

        db_addon = ServiceAddon(**addon_data.model_dump())
        db.add(db_addon)
        await db.commit()
        await db.refresh(db_addon)
        return db_addon

    @staticmethod
    async def update_addon(
        db: AsyncSession,
        addon_id: int,
        business_id: int,
        addon_data: ServiceAddonUpdate,
    ) -> Optional[ServiceAddon]:
        """Update a service add-on."""
        db_addon = await ServiceAddonService.get_addon(db, addon_id, business_id)
        if not db_addon:
            return None

        update_data = addon_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_addon, field, value)

        await db.commit()
        await db.refresh(db_addon)
        return db_addon

    @staticmethod
    async def update_addon_by_uuid(
        db: AsyncSession,
        addon_uuid: UUID,
        business_id: int,
        addon_data: ServiceAddonUpdate,
    ) -> Optional[ServiceAddon]:
        """Update a service add-on by UUID."""
        db_addon = await ServiceAddonService.get_addon_by_uuid(
            db, addon_uuid, business_id
        )
        if not db_addon:
            return None

        update_data = addon_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_addon, field, value)

        await db.commit()
        await db.refresh(db_addon)
        return db_addon

    @staticmethod
    async def delete_addon(db: AsyncSession, addon_id: int, business_id: int) -> bool:
        """Delete a service add-on."""
        db_addon = await ServiceAddonService.get_addon(db, addon_id, business_id)
        if not db_addon:
            return False

        await db.delete(db_addon)
        await db.commit()
        return True

    @staticmethod
    async def delete_addon_by_uuid(
        db: AsyncSession, addon_uuid: UUID, business_id: int
    ) -> bool:
        """Delete a service add-on by UUID."""
        db_addon = await ServiceAddonService.get_addon_by_uuid(
            db, addon_uuid, business_id
        )
        if not db_addon:
            return False

        await db.delete(db_addon)
        await db.commit()
        return True


class StaffServiceMappingService:
    """Business logic for staff-service mappings."""

    @staticmethod
    async def get_staff_services(
        db: AsyncSession,
        staff_id: Optional[int] = None,
        service_id: Optional[int] = None,
    ) -> list[StaffService]:
        """Get staff-service mappings."""
        stmt = select(StaffService)
        if staff_id is not None:
            stmt = stmt.filter(StaffService.staff_id == staff_id)
        if service_id is not None:
            stmt = stmt.filter(StaffService.service_id == service_id)

        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_staff_service(
        db: AsyncSession, staff_service_id: int
    ) -> Optional[StaffService]:
        """Get a single staff-service mapping."""
        stmt = select(StaffService).filter(StaffService.id == staff_service_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_staff_service_by_uuid(
        db: AsyncSession, staff_service_uuid: UUID
    ) -> Optional[StaffService]:
        """Get a single staff-service mapping by UUID."""
        stmt = select(StaffService).filter(StaffService.uuid == staff_service_uuid)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_staff_service(
        db: AsyncSession, mapping_data: StaffServiceCreate
    ) -> StaffService:
        """Create a new staff-service mapping."""
        # Check if mapping already exists
        existing_stmt = select(StaffService).filter(
            and_(
                StaffService.staff_id == mapping_data.staff_id,
                StaffService.service_id == mapping_data.service_id,
            )
        )
        existing_result = await db.execute(existing_stmt)
        if existing_result.first():
            raise HTTPException(
                status_code=400, detail="Staff-service mapping already exists"
            )

        db_mapping = StaffService(**mapping_data.model_dump())
        db.add(db_mapping)
        await db.commit()
        await db.refresh(db_mapping)
        return db_mapping

    @staticmethod
    async def update_staff_service(
        db: AsyncSession, staff_service_id: int, mapping_data: StaffServiceUpdate
    ) -> Optional[StaffService]:
        """Update a staff-service mapping."""
        db_mapping = await StaffServiceMappingService.get_staff_service(
            db, staff_service_id
        )
        if not db_mapping:
            return None

        update_data = mapping_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_mapping, field, value)

        await db.commit()
        await db.refresh(db_mapping)
        return db_mapping

    @staticmethod
    async def update_staff_service_by_uuid(
        db: AsyncSession, staff_service_uuid: UUID, mapping_data: StaffServiceUpdate
    ) -> Optional[StaffService]:
        """Update a staff-service mapping by UUID."""
        db_mapping = await StaffServiceMappingService.get_staff_service_by_uuid(
            db, staff_service_uuid
        )
        if not db_mapping:
            return None

        update_data = mapping_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_mapping, field, value)

        await db.commit()
        await db.refresh(db_mapping)
        return db_mapping

    @staticmethod
    async def delete_staff_service(db: AsyncSession, staff_service_id: int) -> bool:
        """Delete a staff-service mapping."""
        db_mapping = await StaffServiceMappingService.get_staff_service(
            db, staff_service_id
        )
        if not db_mapping:
            return False

        await db.delete(db_mapping)
        await db.commit()
        return True

    @staticmethod
    async def delete_staff_service_by_uuid(
        db: AsyncSession, staff_service_uuid: UUID
    ) -> bool:
        """Delete a staff-service mapping by UUID."""
        db_mapping = await StaffServiceMappingService.get_staff_service_by_uuid(
            db, staff_service_uuid
        )
        if not db_mapping:
            return False

        await db.delete(db_mapping)
        await db.commit()
        return True
