import pytest
from decimal import Decimal
from app.models.service import Service
from app.models.service_category import ServiceCategory
from app.models.service_addon import ServiceAddon
from app.models.staff_service import StaffService
from app.models.business import Business
from app.models.staff import Staff


class TestServiceCategory:
    """Test service category model."""

    def test_service_category_creation(self):
        """Test creating a service category."""
        category = ServiceCategory(
            business_id=1,
            name="Hair Services",
            description="All hair-related services",
            sort_order=1,
            is_active=True,
            icon="scissors",
            color="#FF5733"
        )
        
        assert category.name == "Hair Services"
        assert category.description == "All hair-related services"
        assert category.business_id == 1
        assert category.sort_order == 1
        assert category.is_active is True
        assert category.icon == "scissors"
        assert category.color == "#FF5733"

    def test_service_category_repr(self):
        """Test service category string representation."""
        category = ServiceCategory(
            id=1,
            business_id=1,
            name="Hair Services"
        )
        
        expected = "<ServiceCategory(id=1, name='Hair Services', business_id=1)>"
        assert repr(category) == expected


class TestService:
    """Test service model."""

    def test_service_creation(self):
        """Test creating a service."""
        service = Service(
            business_id=1,
            category_id=1,
            name="Haircut",
            description="Basic haircut service",
            duration_minutes=30,
            price=Decimal("25.00"),
            buffer_before_minutes=5,
            buffer_after_minutes=10,
            is_active=True,
            requires_deposit=False,
            sort_order=1
        )
        
        assert service.name == "Haircut"
        assert service.duration_minutes == 30
        assert service.price == Decimal("25.00")
        assert service.buffer_before_minutes == 5
        assert service.buffer_after_minutes == 10
        assert service.is_active is True
        assert service.requires_deposit is False

    def test_service_total_duration_property(self):
        """Test total duration calculation including buffers."""
        service = Service(
            duration_minutes=30,
            buffer_before_minutes=5,
            buffer_after_minutes=10
        )
        
        assert service.total_duration_minutes == 45

    def test_service_repr(self):
        """Test service string representation."""
        service = Service(
            id=1,
            name="Haircut",
            duration_minutes=30,
            price=Decimal("25.00")
        )
        
        expected = "<Service(id=1, name='Haircut', duration=30min, price=$25.00)>"
        assert repr(service) == expected


class TestServiceAddon:
    """Test service add-on model."""

    def test_service_addon_creation(self):
        """Test creating a service add-on."""
        addon = ServiceAddon(
            business_id=1,
            service_id=1,
            name="Hair Wash",
            description="Shampoo and conditioning",
            extra_duration_minutes=15,
            price=Decimal("5.00"),
            is_active=True,
            is_required=False,
            max_quantity=1,
            sort_order=1
        )
        
        assert addon.name == "Hair Wash"
        assert addon.extra_duration_minutes == 15
        assert addon.price == Decimal("5.00")
        assert addon.is_active is True
        assert addon.is_required is False
        assert addon.max_quantity == 1

    def test_service_addon_repr(self):
        """Test service add-on string representation."""
        addon = ServiceAddon(
            id=1,
            name="Hair Wash",
            service_id=1,
            price=Decimal("5.00")
        )
        
        expected = "<ServiceAddon(id=1, name='Hair Wash', service_id=1, price=$5.00)>"
        assert repr(addon) == expected


class TestStaffService:
    """Test staff-service mapping model."""

    def test_staff_service_creation(self):
        """Test creating a staff-service mapping."""
        staff_service = StaffService(
            staff_id=1,
            service_id=1,
            override_duration_minutes=35,
            override_price=Decimal("30.00"),
            override_buffer_before_minutes=10,
            override_buffer_after_minutes=5,
            is_available=True,
            expertise_level="senior",
            notes="Specializes in modern cuts",
            requires_approval=False
        )
        
        assert staff_service.staff_id == 1
        assert staff_service.service_id == 1
        assert staff_service.override_duration_minutes == 35
        assert staff_service.override_price == Decimal("30.00")
        assert staff_service.is_available is True
        assert staff_service.expertise_level == "senior"

    def test_staff_service_effective_properties_with_overrides(self):
        """Test effective property calculations with overrides."""
        from app.models.service import Service
        
        # Create a real service for testing
        service = Service(
            business_id=1,
            name="Test Service",
            duration_minutes=30,
            price=Decimal("25.00"),
            buffer_before_minutes=5,
            buffer_after_minutes=10
        )
        
        staff_service = StaffService(
            staff_id=1,
            service_id=1,
            override_duration_minutes=35,
            override_price=Decimal("30.00"),
            override_buffer_before_minutes=7,
            override_buffer_after_minutes=8
        )
        staff_service.service = service
        
        assert staff_service.effective_duration_minutes == 35
        assert staff_service.effective_price == Decimal("30.00")
        assert staff_service.effective_buffer_before_minutes == 7
        assert staff_service.effective_buffer_after_minutes == 8
        assert staff_service.effective_total_duration_minutes == 50  # 35 + 7 + 8

    def test_staff_service_effective_properties_without_overrides(self):
        """Test effective property calculations without overrides."""
        from app.models.service import Service
        
        # Create a real service for testing
        service = Service(
            business_id=1,
            name="Test Service",
            duration_minutes=30,
            price=Decimal("25.00"),
            buffer_before_minutes=5,
            buffer_after_minutes=10
        )
        
        staff_service = StaffService(
            staff_id=1,
            service_id=1,
            is_available=True
        )
        staff_service.service = service
        
        assert staff_service.effective_duration_minutes == 30
        assert staff_service.effective_price == Decimal("25.00")
        assert staff_service.effective_buffer_before_minutes == 5
        assert staff_service.effective_buffer_after_minutes == 10
        assert staff_service.effective_total_duration_minutes == 45  # 30 + 5 + 10

    def test_staff_service_repr(self):
        """Test staff-service mapping string representation."""
        staff_service = StaffService(
            id=1,
            staff_id=1,
            service_id=1,
            is_available=True
        )
        
        expected = "<StaffService(id=1, staff_id=1, service_id=1, available=True)>"
        assert repr(staff_service) == expected