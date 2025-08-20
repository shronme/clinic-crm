import pytest
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.service import StaffServiceMappingService
from app.schemas.service import StaffServiceCreate, StaffServiceUpdate
from app.models.staff import Staff
from app.models.service import Service
from app.models.staff_service import StaffService
from tests.fixtures.service_fixtures import (
    sample_business, sample_staff, sample_service, sample_staff_service, 
    multiple_staff_members, multiple_services
)


class TestStaffServiceMappingService:
    """Test staff-service mapping business logic."""

    async def test_get_staff_services_all(self, db: AsyncSession, multiple_staff_members: list[Staff], sample_service: Service):
        """Test getting all staff-service mappings."""
        # Create mappings for testing
        mappings = []
        for i, staff in enumerate(multiple_staff_members):
            mapping = StaffService(
                staff_id=staff.id,
                service_id=sample_service.id,
                is_available=True,
                expertise_level=f"level_{i}"
            )
            mappings.append(mapping)
        
        db.add_all(mappings)
        await db.commit()
        
        staff_services = await StaffServiceMappingService.get_staff_services(db)
        
        assert len(staff_services) >= 3  # At least the ones we created
        mapping_levels = [ss.expertise_level for ss in staff_services]
        assert "level_0" in mapping_levels
        assert "level_1" in mapping_levels
        assert "level_2" in mapping_levels

    async def test_get_staff_services_by_staff(self, db: AsyncSession, sample_staff: Staff, multiple_services: list[Service]):
        """Test getting staff-service mappings filtered by staff."""
        # Create mappings for one staff member across multiple services
        mappings = []
        for service in multiple_services:
            mapping = StaffService(
                staff_id=sample_staff.id,
                service_id=service.id,
                is_available=True
            )
            mappings.append(mapping)
        
        db.add_all(mappings)
        await db.commit()
        
        staff_services = await StaffServiceMappingService.get_staff_services(db, staff_id=sample_staff.id)
        
        assert len(staff_services) == 3  # One for each service
        assert all(ss.staff_id == sample_staff.id for ss in staff_services)

    async def test_get_staff_services_by_service(self, db: AsyncSession, multiple_staff_members: list[Staff], sample_service: Service):
        """Test getting staff-service mappings filtered by service."""
        # Create mappings for multiple staff for one service
        mappings = []
        for staff in multiple_staff_members:
            mapping = StaffService(
                staff_id=staff.id,
                service_id=sample_service.id,
                is_available=True
            )
            mappings.append(mapping)
        
        db.add_all(mappings)
        await db.commit()
        
        staff_services = await StaffServiceMappingService.get_staff_services(db, service_id=sample_service.id)
        
        assert len(staff_services) == 3  # One for each staff
        assert all(ss.service_id == sample_service.id for ss in staff_services)

    async def test_get_staff_service_success(self, db: AsyncSession, sample_staff_service: StaffService):
        """Test getting a single staff-service mapping successfully."""
        mapping = await StaffServiceMappingService.get_staff_service(db, sample_staff_service.id)
        
        assert mapping is not None
        assert mapping.id == sample_staff_service.id
        assert mapping.staff_id == sample_staff_service.staff_id
        assert mapping.service_id == sample_staff_service.service_id

    async def test_get_staff_service_not_found(self, db: AsyncSession):
        """Test getting a non-existent staff-service mapping."""
        mapping = await StaffServiceMappingService.get_staff_service(db, 99999)
        
        assert mapping is None

    async def test_create_staff_service_success(self, db: AsyncSession, sample_staff: Staff, sample_service: Service):
        """Test creating a staff-service mapping successfully."""
        mapping_data = StaffServiceCreate(
            staff_id=sample_staff.id,
            service_id=sample_service.id,
            override_duration_minutes=40,
            override_price=Decimal("35.00"),
            override_buffer_before_minutes=8,
            override_buffer_after_minutes=12,
            is_available=True,
            expertise_level="expert",
            notes="Master of this service",
            requires_approval=True
        )
        
        mapping = await StaffServiceMappingService.create_staff_service(db, mapping_data)
        
        assert mapping.id is not None
        assert mapping.staff_id == sample_staff.id
        assert mapping.service_id == sample_service.id
        assert mapping.override_duration_minutes == 40
        assert mapping.override_price == Decimal("35.00")
        assert mapping.override_buffer_before_minutes == 8
        assert mapping.override_buffer_after_minutes == 12
        assert mapping.is_available is True
        assert mapping.expertise_level == "expert"
        assert mapping.notes == "Master of this service"
        assert mapping.requires_approval is True

    async def test_create_staff_service_minimal(self, db: AsyncSession, sample_staff: Staff, sample_service: Service):
        """Test creating a staff-service mapping with minimal data."""
        mapping_data = StaffServiceCreate(
            staff_id=sample_staff.id,
            service_id=sample_service.id
        )
        
        mapping = await StaffServiceMappingService.create_staff_service(db, mapping_data)
        
        assert mapping.staff_id == sample_staff.id
        assert mapping.service_id == sample_service.id
        assert mapping.is_available is True  # Default
        assert mapping.requires_approval is False  # Default
        assert mapping.override_duration_minutes is None
        assert mapping.override_price is None

    async def test_create_staff_service_duplicate(self, db: AsyncSession, sample_staff_service: StaffService):
        """Test creating a duplicate staff-service mapping."""
        mapping_data = StaffServiceCreate(
            staff_id=sample_staff_service.staff_id,
            service_id=sample_staff_service.service_id
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await StaffServiceMappingService.create_staff_service(db, mapping_data)
        
        assert exc_info.value.status_code == 400
        assert "Staff-service mapping already exists" in str(exc_info.value.detail)

    async def test_update_staff_service_success(self, db: AsyncSession, sample_staff_service: StaffService):
        """Test updating a staff-service mapping successfully."""
        update_data = StaffServiceUpdate(
            override_duration_minutes=50,
            override_price=Decimal("40.00"),
            is_available=False,
            expertise_level="master",
            notes="Updated expertise level"
        )
        
        updated_mapping = await StaffServiceMappingService.update_staff_service(
            db, sample_staff_service.id, update_data
        )
        
        assert updated_mapping is not None
        assert updated_mapping.override_duration_minutes == 50
        assert updated_mapping.override_price == Decimal("40.00")
        assert updated_mapping.is_available is False
        assert updated_mapping.expertise_level == "master"
        assert updated_mapping.notes == "Updated expertise level"
        # Original values should remain
        assert updated_mapping.staff_id == sample_staff_service.staff_id
        assert updated_mapping.service_id == sample_staff_service.service_id

    async def test_update_staff_service_partial(self, db: AsyncSession, sample_staff_service: StaffService):
        """Test partial staff-service mapping update."""
        original_expertise = sample_staff_service.expertise_level
        original_price = sample_staff_service.override_price
        
        update_data = StaffServiceUpdate(
            notes="Only updating notes"
        )
        
        updated_mapping = await StaffServiceMappingService.update_staff_service(
            db, sample_staff_service.id, update_data
        )
        
        assert updated_mapping is not None
        assert updated_mapping.notes == "Only updating notes"
        # Other fields should remain unchanged
        assert updated_mapping.expertise_level == original_expertise
        assert updated_mapping.override_price == original_price

    async def test_update_staff_service_not_found(self, db: AsyncSession):
        """Test updating a non-existent staff-service mapping."""
        update_data = StaffServiceUpdate(notes="Updated")
        
        result = await StaffServiceMappingService.update_staff_service(db, 99999, update_data)
        
        assert result is None

    async def test_delete_staff_service_success(self, db: AsyncSession, sample_staff_service: StaffService):
        """Test deleting a staff-service mapping successfully."""
        result = await StaffServiceMappingService.delete_staff_service(db, sample_staff_service.id)
        
        assert result is True
        
        # Verify mapping is deleted
        deleted_mapping = await StaffServiceMappingService.get_staff_service(db, sample_staff_service.id)
        assert deleted_mapping is None

    async def test_delete_staff_service_not_found(self, db: AsyncSession):
        """Test deleting a non-existent staff-service mapping."""
        result = await StaffServiceMappingService.delete_staff_service(db, 99999)
        
        assert result is False

    async def test_effective_properties_with_overrides(self, db: AsyncSession, sample_staff: Staff):
        """Test effective property calculations with overrides."""
        # Create a service with base values
        service = Service(
            business_id=1,
            name="Test Service",
            duration_minutes=30,
            price=Decimal("25.00"),
            buffer_before_minutes=5,
            buffer_after_minutes=10
        )
        db.add(service)
        await db.commit()
        await db.refresh(service)
        
        # Create staff service with overrides
        mapping_data = StaffServiceCreate(
            staff_id=sample_staff.id,
            service_id=service.id,
            override_duration_minutes=35,
            override_price=Decimal("30.00"),
            override_buffer_before_minutes=7,
            override_buffer_after_minutes=8
        )
        
        mapping = await StaffServiceMappingService.create_staff_service(db, mapping_data)
        
        # Load the service relationship for effective properties
        await db.refresh(mapping, ['service'])
        
        # Test effective properties use overrides
        assert mapping.effective_duration_minutes == 35
        assert mapping.effective_price == Decimal("30.00")
        assert mapping.effective_buffer_before_minutes == 7
        assert mapping.effective_buffer_after_minutes == 8
        assert mapping.effective_total_duration_minutes == 50  # 35 + 7 + 8

    async def test_effective_properties_without_overrides(self, db: AsyncSession, sample_staff: Staff):
        """Test effective property calculations without overrides."""
        # Create a service with base values
        service = Service(
            business_id=1,
            name="Test Service",
            duration_minutes=30,
            price=Decimal("25.00"),
            buffer_before_minutes=5,
            buffer_after_minutes=10
        )
        db.add(service)
        await db.commit()
        await db.refresh(service)
        
        # Create staff service without overrides
        mapping_data = StaffServiceCreate(
            staff_id=sample_staff.id,
            service_id=service.id,
            is_available=True
        )
        
        mapping = await StaffServiceMappingService.create_staff_service(db, mapping_data)
        
        # Load the service relationship for effective properties
        await db.refresh(mapping, ['service'])
        
        # Test effective properties use service defaults
        assert mapping.effective_duration_minutes == 30
        assert mapping.effective_price == Decimal("25.00")
        assert mapping.effective_buffer_before_minutes == 5
        assert mapping.effective_buffer_after_minutes == 10
        assert mapping.effective_total_duration_minutes == 45  # 30 + 5 + 10