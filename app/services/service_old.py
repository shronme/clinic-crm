from typing import Optional

from fastapi import HTTPException
from sqlalchemy import and_
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
        query = db.query(ServiceCategory).filter(
            ServiceCategory.business_id == business_id
        )
        if parent_id is not None:
            query = query.filter(ServiceCategory.parent_id == parent_id)
        else:
            query = query.filter(ServiceCategory.parent_id.is_(None))
        return query.order_by(ServiceCategory.sort_order, ServiceCategory.name).all()

    @staticmethod
    def get_category(
        db: AsyncSession, category_id: int, business_id: int
    ) -> Optional[ServiceCategory]:
        """Get a single service category."""
        return (
            db.query(ServiceCategory)
            .filter(
                and_(
                    ServiceCategory.id == category_id,
                    ServiceCategory.business_id == business_id,
                )
            )
            .first()
        )

    @staticmethod
    def create_category(
        db: AsyncSession, category_data: ServiceCategoryCreate
    ) -> ServiceCategory:
        """Create a new service category."""
        # Validate parent category exists and belongs to same business
        if category_data.parent_id:
            parent = ServiceCategoryService.get_category(
                db, category_data.parent_id, category_data.business_id
            )
            if not parent:
                raise HTTPException(status_code=400, detail="Parent category not found")

        db_category = ServiceCategory(**category_data.model_dump())
        db.add(db_category)
        db.commit()
        db.refresh(db_category)
        return db_category

    @staticmethod
    def update_category(
        db: AsyncSession,
        category_id: int,
        business_id: int,
        category_data: ServiceCategoryUpdate,
    ) -> Optional[ServiceCategory]:
        """Update a service category."""
        db_category = ServiceCategoryService.get_category(db, category_id, business_id)
        if not db_category:
            return None

        # Validate parent category if being updated
        if category_data.parent_id:
            if category_data.parent_id == category_id:
                raise HTTPException(
                    status_code=400, detail="Category cannot be its own parent"
                )
            parent = ServiceCategoryService.get_category(
                db, category_data.parent_id, business_id
            )
            if not parent:
                raise HTTPException(status_code=400, detail="Parent category not found")

        update_data = category_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_category, field, value)

        db.commit()
        db.refresh(db_category)
        return db_category

    @staticmethod
    def delete_category(db: AsyncSession, category_id: int, business_id: int) -> bool:
        """Delete a service category."""
        db_category = ServiceCategoryService.get_category(db, category_id, business_id)
        if not db_category:
            return False

        # Check for child categories
        children = (
            db.query(ServiceCategory)
            .filter(ServiceCategory.parent_id == category_id)
            .first()
        )
        if children:
            raise HTTPException(
                status_code=400, detail="Cannot delete category with child categories"
            )

        # Check for services using this category
        services = db.query(Service).filter(Service.category_id == category_id).first()
        if services:
            raise HTTPException(
                status_code=400,
                detail="Cannot delete category with associated services",
            )

        db.delete(db_category)
        db.commit()
        return True


class ServiceManagementService:
    """Business logic for services."""

    @staticmethod
    def get_services(
        db: AsyncSession,
        business_id: int,
        category_id: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> list[Service]:
        """Get services, optionally filtered by category and status."""
        query = db.query(Service).filter(Service.business_id == business_id)
        if category_id is not None:
            query = query.filter(Service.category_id == category_id)
        if is_active is not None:
            query = query.filter(Service.is_active == is_active)
        return query.order_by(Service.sort_order, Service.name).all()

    @staticmethod
    def get_service(
        db: AsyncSession, service_id: int, business_id: int
    ) -> Optional[Service]:
        """Get a single service."""
        return (
            db.query(Service)
            .filter(and_(Service.id == service_id, Service.business_id == business_id))
            .first()
        )

    @staticmethod
    def create_service(db: AsyncSession, service_data: ServiceCreate) -> Service:
        """Create a new service."""
        # Validate category exists if provided
        if service_data.category_id:
            category = ServiceCategoryService.get_category(
                db, service_data.category_id, service_data.business_id
            )
            if not category:
                raise HTTPException(status_code=400, detail="Category not found")

        db_service = Service(**service_data.model_dump())
        db.add(db_service)
        db.commit()
        db.refresh(db_service)
        return db_service

    @staticmethod
    def update_service(
        db: AsyncSession, service_id: int, business_id: int, service_data: ServiceUpdate
    ) -> Optional[Service]:
        """Update a service."""
        db_service = ServiceManagementService.get_service(db, service_id, business_id)
        if not db_service:
            return None

        # Validate category if being updated
        if service_data.category_id:
            category = ServiceCategoryService.get_category(
                db, service_data.category_id, business_id
            )
            if not category:
                raise HTTPException(status_code=400, detail="Category not found")

        update_data = service_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_service, field, value)

        db.commit()
        db.refresh(db_service)
        return db_service

    @staticmethod
    def delete_service(db: AsyncSession, service_id: int, business_id: int) -> bool:
        """Delete a service."""
        db_service = ServiceManagementService.get_service(db, service_id, business_id)
        if not db_service:
            return False

        # Check for associated staff services
        staff_services = (
            db.query(StaffService).filter(StaffService.service_id == service_id).first()
        )
        if staff_services:
            raise HTTPException(
                status_code=400, detail="Cannot delete service with staff assignments"
            )

        db.delete(db_service)
        db.commit()
        return True


class ServiceAddonService:
    """Business logic for service add-ons."""

    @staticmethod
    def get_addons(
        db: AsyncSession, business_id: int, service_id: Optional[int] = None
    ) -> list[ServiceAddon]:
        """Get service add-ons, optionally filtered by service."""
        query = db.query(ServiceAddon).filter(ServiceAddon.business_id == business_id)
        if service_id is not None:
            query = query.filter(ServiceAddon.service_id == service_id)
        return query.order_by(ServiceAddon.sort_order, ServiceAddon.name).all()

    @staticmethod
    def get_addon(
        db: AsyncSession, addon_id: int, business_id: int
    ) -> Optional[ServiceAddon]:
        """Get a single service add-on."""
        return (
            db.query(ServiceAddon)
            .filter(
                and_(
                    ServiceAddon.id == addon_id, ServiceAddon.business_id == business_id
                )
            )
            .first()
        )

    @staticmethod
    def create_addon(db: AsyncSession, addon_data: ServiceAddonCreate) -> ServiceAddon:
        """Create a new service add-on."""
        # Validate service exists
        service = ServiceManagementService.get_service(
            db, addon_data.service_id, addon_data.business_id
        )
        if not service:
            raise HTTPException(status_code=400, detail="Service not found")

        db_addon = ServiceAddon(**addon_data.model_dump())
        db.add(db_addon)
        db.commit()
        db.refresh(db_addon)
        return db_addon

    @staticmethod
    def update_addon(
        db: AsyncSession,
        addon_id: int,
        business_id: int,
        addon_data: ServiceAddonUpdate,
    ) -> Optional[ServiceAddon]:
        """Update a service add-on."""
        db_addon = ServiceAddonService.get_addon(db, addon_id, business_id)
        if not db_addon:
            return None

        update_data = addon_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_addon, field, value)

        db.commit()
        db.refresh(db_addon)
        return db_addon

    @staticmethod
    def delete_addon(db: AsyncSession, addon_id: int, business_id: int) -> bool:
        """Delete a service add-on."""
        db_addon = ServiceAddonService.get_addon(db, addon_id, business_id)
        if not db_addon:
            return False

        db.delete(db_addon)
        db.commit()
        return True


class StaffServiceMappingService:
    """Business logic for staff-service mappings."""

    @staticmethod
    def get_staff_services(
        db: AsyncSession,
        staff_id: Optional[int] = None,
        service_id: Optional[int] = None,
    ) -> list[StaffService]:
        """Get staff-service mappings."""
        query = db.query(StaffService)
        if staff_id is not None:
            query = query.filter(StaffService.staff_id == staff_id)
        if service_id is not None:
            query = query.filter(StaffService.service_id == service_id)
        return query.all()

    @staticmethod
    def get_staff_service(
        db: AsyncSession, staff_service_id: int
    ) -> Optional[StaffService]:
        """Get a single staff-service mapping."""
        return (
            db.query(StaffService).filter(StaffService.id == staff_service_id).first()
        )

    @staticmethod
    def create_staff_service(
        db: AsyncSession, mapping_data: StaffServiceCreate
    ) -> StaffService:
        """Create a new staff-service mapping."""
        # Check if mapping already exists
        existing = (
            db.query(StaffService)
            .filter(
                and_(
                    StaffService.staff_id == mapping_data.staff_id,
                    StaffService.service_id == mapping_data.service_id,
                )
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=400, detail="Staff-service mapping already exists"
            )

        db_mapping = StaffService(**mapping_data.model_dump())
        db.add(db_mapping)
        db.commit()
        db.refresh(db_mapping)
        return db_mapping

    @staticmethod
    def update_staff_service(
        db: AsyncSession, staff_service_id: int, mapping_data: StaffServiceUpdate
    ) -> Optional[StaffService]:
        """Update a staff-service mapping."""
        db_mapping = StaffServiceMappingService.get_staff_service(db, staff_service_id)
        if not db_mapping:
            return None

        update_data = mapping_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_mapping, field, value)

        db.commit()
        db.refresh(db_mapping)
        return db_mapping

    @staticmethod
    def delete_staff_service(db: AsyncSession, staff_service_id: int) -> bool:
        """Delete a staff-service mapping."""
        db_mapping = StaffServiceMappingService.get_staff_service(db, staff_service_id)
        if not db_mapping:
            return False

        db.delete(db_mapping)
        db.commit()
        return True
