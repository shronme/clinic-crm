from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.service import Service
from app.models.service_category import ServiceCategory
from app.schemas.service import ServiceCreate, ServiceUpdate
from app.services.service import ServiceManagementService


class TestServiceManagementService:
    """Test service management business logic."""

    async def test_get_services_all(
        self, db: AsyncSession, multiple_services: list[Service]
    ):
        """Test getting all services for a business."""
        business_id = multiple_services[0].business_id

        services = await ServiceManagementService.get_services(db, business_id)

        assert len(services) == 3  # basic_cut, premium_cut, inactive_service
        service_names = [s.name for s in services]
        assert "Basic Cut" in service_names
        assert "Premium Cut" in service_names
        assert "Inactive Service" in service_names

    async def test_get_services_by_category(
        self, db: AsyncSession, multiple_services: list[Service]
    ):
        """Test getting services filtered by category."""
        business_id = multiple_services[0].business_id
        category_id = multiple_services[0].category_id

        services = await ServiceManagementService.get_services(
            db, business_id, category_id=category_id
        )

        assert len(services) == 3
        assert all(s.category_id == category_id for s in services)

    async def test_get_services_active_only(
        self, db: AsyncSession, multiple_services: list[Service]
    ):
        """Test getting only active services."""
        business_id = multiple_services[0].business_id

        services = await ServiceManagementService.get_services(
            db, business_id, is_active=True
        )

        assert len(services) == 2  # Only active services
        assert all(s.is_active for s in services)
        service_names = [s.name for s in services]
        assert "Inactive Service" not in service_names

    async def test_get_services_inactive_only(
        self, db: AsyncSession, multiple_services: list[Service]
    ):
        """Test getting only inactive services."""
        business_id = multiple_services[0].business_id

        services = await ServiceManagementService.get_services(
            db, business_id, is_active=False
        )

        assert len(services) == 1
        assert not services[0].is_active
        assert services[0].name == "Inactive Service"

    async def test_get_service_success(self, db: AsyncSession, sample_service: Service):
        """Test getting a single service successfully."""
        service = await ServiceManagementService.get_service(
            db, sample_service.id, sample_service.business_id
        )

        assert service is not None
        assert service.id == sample_service.id
        assert service.name == sample_service.name

    async def test_get_service_not_found(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test getting a non-existent service."""
        service = await ServiceManagementService.get_service(
            db, 99999, sample_business.id
        )

        assert service is None

    async def test_get_service_wrong_business(
        self, db: AsyncSession, sample_service: Service
    ):
        """Test getting a service from wrong business."""
        service = await ServiceManagementService.get_service(
            db,
            sample_service.id,
            99999,  # Wrong business ID
        )

        assert service is None

    async def test_create_service_success(
        self,
        db: AsyncSession,
        sample_business: Business,
        sample_service_category: ServiceCategory,
    ):
        """Test creating a service successfully."""
        service_data = ServiceCreate(
            business_id=sample_business.id,
            category_id=sample_service_category.id,
            name="New Service",
            description="Test service",
            duration_minutes=45,
            price=Decimal("35.00"),
            buffer_before_minutes=10,
            buffer_after_minutes=5,
            is_active=True,
            requires_deposit=True,
            deposit_amount=Decimal("10.00"),
            sort_order=5,
        )

        service = await ServiceManagementService.create_service(db, service_data)

        assert service.id is not None
        assert service.name == "New Service"
        assert service.duration_minutes == 45
        assert service.price == Decimal("35.00")
        assert service.requires_deposit is True
        assert service.deposit_amount == Decimal("10.00")
        assert service.total_duration_minutes == 60  # 45 + 10 + 5

    async def test_create_service_without_category(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test creating a service without category."""
        service_data = ServiceCreate(
            business_id=sample_business.id,
            name="Uncategorized Service",
            duration_minutes=30,
            price=Decimal("25.00"),
        )

        service = await ServiceManagementService.create_service(db, service_data)

        assert service.category_id is None
        assert service.name == "Uncategorized Service"

    async def test_create_service_invalid_category(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test creating a service with invalid category."""
        service_data = ServiceCreate(
            business_id=sample_business.id,
            category_id=99999,  # Non-existent category
            name="Invalid Category Service",
            duration_minutes=30,
            price=Decimal("25.00"),
        )

        with pytest.raises(HTTPException) as exc_info:
            await ServiceManagementService.create_service(db, service_data)

        assert exc_info.value.status_code == 400
        assert "Category not found" in str(exc_info.value.detail)

    async def test_update_service_success(
        self, db: AsyncSession, sample_service: Service
    ):
        """Test updating a service successfully."""
        update_data = ServiceUpdate(
            name="Updated Service",
            price=Decimal("30.00"),
            duration_minutes=35,
            is_active=False,
        )

        updated_service = await ServiceManagementService.update_service(
            db, sample_service.id, sample_service.business_id, update_data
        )

        assert updated_service is not None
        assert updated_service.name == "Updated Service"
        assert updated_service.price == Decimal("30.00")
        assert updated_service.duration_minutes == 35
        assert updated_service.is_active is False
        # Original values should remain
        assert updated_service.description == sample_service.description

    async def test_update_service_not_found(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test updating a non-existent service."""
        update_data = ServiceUpdate(name="Updated")

        result = await ServiceManagementService.update_service(
            db, 99999, sample_business.id, update_data
        )

        assert result is None

    async def test_update_service_invalid_category(
        self, db: AsyncSession, sample_service: Service
    ):
        """Test updating a service with invalid category."""
        update_data = ServiceUpdate(category_id=99999)

        with pytest.raises(HTTPException) as exc_info:
            await ServiceManagementService.update_service(
                db, sample_service.id, sample_service.business_id, update_data
            )

        assert exc_info.value.status_code == 400
        assert "Category not found" in str(exc_info.value.detail)

    async def test_delete_service_success(
        self, db: AsyncSession, sample_service: Service
    ):
        """Test deleting a service successfully."""
        result = await ServiceManagementService.delete_service(
            db, sample_service.id, sample_service.business_id
        )

        assert result is True

        # Verify service is deleted
        deleted_service = await ServiceManagementService.get_service(
            db, sample_service.id, sample_service.business_id
        )
        assert deleted_service is None

    async def test_delete_service_not_found(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test deleting a non-existent service."""
        result = await ServiceManagementService.delete_service(
            db, 99999, sample_business.id
        )

        assert result is False

    async def test_delete_service_with_staff_assignments(
        self, db: AsyncSession, sample_service: Service, sample_staff_service
    ):
        """Test deleting a service that has staff assignments."""
        # The sample_staff_service fixture creates a staff service with sample_service

        with pytest.raises(HTTPException) as exc_info:
            await ServiceManagementService.delete_service(
                db, sample_service.id, sample_service.business_id
            )

        assert exc_info.value.status_code == 400
        assert "Cannot delete service with staff assignments" in str(
            exc_info.value.detail
        )

    async def test_service_total_duration_calculation(
        self,
        db: AsyncSession,
        sample_business: Business,
        sample_service_category: ServiceCategory,
    ):
        """Test service total duration calculation including buffers."""
        service_data = ServiceCreate(
            business_id=sample_business.id,
            category_id=sample_service_category.id,
            name="Buffer Test Service",
            duration_minutes=30,
            price=Decimal("25.00"),
            buffer_before_minutes=10,
            buffer_after_minutes=15,
        )

        service = await ServiceManagementService.create_service(db, service_data)

        # Test the total duration property
        assert service.total_duration_minutes == 55  # 30 + 10 + 15
