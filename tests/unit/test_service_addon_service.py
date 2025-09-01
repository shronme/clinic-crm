from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.service import Service
from app.models.service_addon import ServiceAddon
from app.schemas.service import ServiceAddonCreate, ServiceAddonUpdate
from app.services.service import ServiceAddonService


class TestServiceAddonService:
    """Test service add-on business logic."""

    async def test_get_addons_all(self, db: AsyncSession, sample_business: Business):
        """Test getting all add-ons for a business."""
        # Create multiple add-ons for testing
        service1 = Service(
            business_id=sample_business.id,
            name="Service 1",
            duration_minutes=30,
            price=Decimal("25.00"),
        )
        service2 = Service(
            business_id=sample_business.id,
            name="Service 2",
            duration_minutes=45,
            price=Decimal("35.00"),
        )
        db.add_all([service1, service2])
        await db.commit()
        await db.refresh(service1)
        await db.refresh(service2)

        addon1 = ServiceAddon(
            business_id=sample_business.id,
            service_id=service1.id,
            name="Add-on 1",
            price=Decimal("5.00"),
        )
        addon2 = ServiceAddon(
            business_id=sample_business.id,
            service_id=service1.id,
            name="Add-on 2",
            price=Decimal("10.00"),
        )
        addon3 = ServiceAddon(
            business_id=sample_business.id,
            service_id=service2.id,
            name="Add-on 3",
            price=Decimal("15.00"),
        )
        db.add_all([addon1, addon2, addon3])
        await db.commit()

        addons = await ServiceAddonService.get_addons(db, sample_business.id)

        assert len(addons) >= 3  # At least the ones we created
        addon_names = [a.name for a in addons]
        assert "Add-on 1" in addon_names
        assert "Add-on 2" in addon_names
        assert "Add-on 3" in addon_names

    async def test_get_addons_by_service(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test getting add-ons filtered by service."""
        # Create service and add-ons
        service = Service(
            business_id=sample_business.id,
            name="Test Service",
            duration_minutes=30,
            price=Decimal("25.00"),
        )
        db.add(service)
        await db.commit()
        await db.refresh(service)

        addon1 = ServiceAddon(
            business_id=sample_business.id,
            service_id=service.id,
            name="Service Add-on 1",
            price=Decimal("5.00"),
        )
        addon2 = ServiceAddon(
            business_id=sample_business.id,
            service_id=service.id,
            name="Service Add-on 2",
            price=Decimal("10.00"),
        )
        db.add_all([addon1, addon2])
        await db.commit()

        addons = await ServiceAddonService.get_addons(
            db, sample_business.id, service_id=service.id
        )

        assert len(addons) == 2
        assert all(a.service_id == service.id for a in addons)

    async def test_get_addon_success(
        self, db: AsyncSession, sample_service_addon: ServiceAddon
    ):
        """Test getting a single add-on successfully."""
        addon = await ServiceAddonService.get_addon(
            db, sample_service_addon.id, sample_service_addon.business_id
        )

        assert addon is not None
        assert addon.id == sample_service_addon.id
        assert addon.name == sample_service_addon.name

    async def test_get_addon_not_found(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test getting a non-existent add-on."""
        addon = await ServiceAddonService.get_addon(db, 99999, sample_business.id)

        assert addon is None

    async def test_get_addon_wrong_business(
        self, db: AsyncSession, sample_service_addon: ServiceAddon
    ):
        """Test getting an add-on from wrong business."""
        addon = await ServiceAddonService.get_addon(
            db,
            sample_service_addon.id,
            99999,  # Wrong business ID
        )

        assert addon is None

    async def test_create_addon_success(
        self, db: AsyncSession, sample_business: Business, sample_service: Service
    ):
        """Test creating an add-on successfully."""
        addon_data = ServiceAddonCreate(
            business_id=sample_business.id,
            service_id=sample_service.id,
            name="New Add-on",
            description="Test add-on",
            extra_duration_minutes=10,
            price=Decimal("8.00"),
            is_active=True,
            is_required=True,
            max_quantity=2,
            sort_order=5,
        )

        addon = await ServiceAddonService.create_addon(db, addon_data)

        assert addon.id is not None
        assert addon.name == "New Add-on"
        assert addon.description == "Test add-on"
        assert addon.extra_duration_minutes == 10
        assert addon.price == Decimal("8.00")
        assert addon.is_active is True
        assert addon.is_required is True
        assert addon.max_quantity == 2
        assert addon.sort_order == 5

    async def test_create_addon_minimal(
        self, db: AsyncSession, sample_business: Business, sample_service: Service
    ):
        """Test creating an add-on with minimal data."""
        addon_data = ServiceAddonCreate(
            business_id=sample_business.id,
            service_id=sample_service.id,
            name="Minimal Add-on",
            price=Decimal("5.00"),
        )

        addon = await ServiceAddonService.create_addon(db, addon_data)

        assert addon.name == "Minimal Add-on"
        assert addon.price == Decimal("5.00")
        assert addon.extra_duration_minutes == 0  # Default
        assert addon.is_active is True  # Default
        assert addon.is_required is False  # Default
        assert addon.max_quantity == 1  # Default

    async def test_create_addon_invalid_service(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test creating an add-on with invalid service."""
        addon_data = ServiceAddonCreate(
            business_id=sample_business.id,
            service_id=99999,  # Non-existent service
            name="Invalid Service Add-on",
            price=Decimal("5.00"),
        )

        with pytest.raises(HTTPException) as exc_info:
            await ServiceAddonService.create_addon(db, addon_data)

        assert exc_info.value.status_code == 400
        assert "Service not found" in str(exc_info.value.detail)

    async def test_update_addon_success(
        self, db: AsyncSession, sample_service_addon: ServiceAddon
    ):
        """Test updating an add-on successfully."""
        update_data = ServiceAddonUpdate(
            name="Updated Add-on",
            price=Decimal("12.00"),
            extra_duration_minutes=20,
            is_active=False,
            max_quantity=3,
        )

        updated_addon = await ServiceAddonService.update_addon(
            db, sample_service_addon.id, sample_service_addon.business_id, update_data
        )

        assert updated_addon is not None
        assert updated_addon.name == "Updated Add-on"
        assert updated_addon.price == Decimal("12.00")
        assert updated_addon.extra_duration_minutes == 20
        assert updated_addon.is_active is False
        assert updated_addon.max_quantity == 3
        # Original values should remain
        assert updated_addon.service_id == sample_service_addon.service_id

    async def test_update_addon_partial(
        self, db: AsyncSession, sample_service_addon: ServiceAddon
    ):
        """Test partial add-on update."""
        original_name = sample_service_addon.name
        original_price = sample_service_addon.price

        update_data = ServiceAddonUpdate(description="Updated description only")

        updated_addon = await ServiceAddonService.update_addon(
            db, sample_service_addon.id, sample_service_addon.business_id, update_data
        )

        assert updated_addon is not None
        assert updated_addon.description == "Updated description only"
        # Other fields should remain unchanged
        assert updated_addon.name == original_name
        assert updated_addon.price == original_price

    async def test_update_addon_not_found(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test updating a non-existent add-on."""
        update_data = ServiceAddonUpdate(name="Updated")

        result = await ServiceAddonService.update_addon(
            db, 99999, sample_business.id, update_data
        )

        assert result is None

    async def test_delete_addon_success(
        self, db: AsyncSession, sample_service_addon: ServiceAddon
    ):
        """Test deleting an add-on successfully."""
        result = await ServiceAddonService.delete_addon(
            db, sample_service_addon.id, sample_service_addon.business_id
        )

        assert result is True

        # Verify add-on is deleted
        deleted_addon = await ServiceAddonService.get_addon(
            db, sample_service_addon.id, sample_service_addon.business_id
        )
        assert deleted_addon is None

    async def test_delete_addon_not_found(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test deleting a non-existent add-on."""
        result = await ServiceAddonService.delete_addon(db, 99999, sample_business.id)

        assert result is False

    async def test_addon_sorting(
        self, db: AsyncSession, sample_business: Business, sample_service: Service
    ):
        """Test that add-ons are returned in sorted order."""
        # Create add-ons with different sort orders
        addon1 = ServiceAddon(
            business_id=sample_business.id,
            service_id=sample_service.id,
            name="Third Add-on",
            price=Decimal("5.00"),
            sort_order=3,
        )
        addon2 = ServiceAddon(
            business_id=sample_business.id,
            service_id=sample_service.id,
            name="First Add-on",
            price=Decimal("5.00"),
            sort_order=1,
        )
        addon3 = ServiceAddon(
            business_id=sample_business.id,
            service_id=sample_service.id,
            name="Second Add-on",
            price=Decimal("5.00"),
            sort_order=2,
        )

        db.add_all([addon1, addon2, addon3])
        await db.commit()

        addons = await ServiceAddonService.get_addons(
            db, sample_business.id, service_id=sample_service.id
        )

        # Should be sorted by sort_order, then by name
        [a.name for a in addons]
        expected_order = ["First Add-on", "Second Add-on", "Third Add-on"]

        # Find our test add-ons in the results
        our_addons = [a for a in addons if a.name in expected_order]
        our_addon_names = [a.name for a in our_addons]

        assert our_addon_names == expected_order
