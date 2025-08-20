import pytest
from decimal import Decimal
from pydantic import ValidationError
from app.schemas.service import (
    ServiceCategoryCreate, ServiceCategoryUpdate,
    ServiceCreate, ServiceUpdate,
    ServiceAddonCreate, ServiceAddonUpdate,
    StaffServiceCreate, StaffServiceUpdate
)


class TestServiceCategorySchemas:
    """Test service category schemas."""

    def test_service_category_create_valid(self):
        """Test valid service category creation."""
        data = {
            "business_id": 1,
            "name": "Hair Services",
            "description": "All hair-related services",
            "sort_order": 1,
            "is_active": True,
            "icon": "scissors",
            "color": "#FF5733"
        }
        
        category = ServiceCategoryCreate(**data)
        assert category.name == "Hair Services"
        assert category.business_id == 1
        assert category.color == "#FF5733"

    def test_service_category_create_invalid_color(self):
        """Test service category creation with invalid color."""
        data = {
            "business_id": 1,
            "name": "Hair Services",
            "color": "invalid-color"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ServiceCategoryCreate(**data)
        
        assert "String should match pattern" in str(exc_info.value)

    def test_service_category_update_partial(self):
        """Test partial service category update."""
        data = {
            "name": "Updated Hair Services",
            "is_active": False
        }
        
        category_update = ServiceCategoryUpdate(**data)
        assert category_update.name == "Updated Hair Services"
        assert category_update.is_active is False
        assert category_update.description is None  # Not provided


class TestServiceSchemas:
    """Test service schemas."""

    def test_service_create_valid(self):
        """Test valid service creation."""
        data = {
            "business_id": 1,
            "name": "Haircut",
            "description": "Basic haircut service",
            "category_id": 1,
            "duration_minutes": 30,
            "price": Decimal("25.00"),
            "buffer_before_minutes": 5,
            "buffer_after_minutes": 10,
            "is_active": True,
            "requires_deposit": True,
            "deposit_amount": Decimal("10.00"),
            "sort_order": 1
        }
        
        service = ServiceCreate(**data)
        assert service.name == "Haircut"
        assert service.duration_minutes == 30
        assert service.price == Decimal("25.00")
        assert service.requires_deposit is True
        assert service.deposit_amount == Decimal("10.00")

    def test_service_create_invalid_duration(self):
        """Test service creation with invalid duration."""
        data = {
            "business_id": 1,
            "name": "Haircut",
            "duration_minutes": 0,  # Invalid: must be > 0
            "price": Decimal("25.00")
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ServiceCreate(**data)
        
        assert "Input should be greater than 0" in str(exc_info.value)

    def test_service_create_negative_price(self):
        """Test service creation with negative price."""
        data = {
            "business_id": 1,
            "name": "Haircut",
            "duration_minutes": 30,
            "price": Decimal("-5.00")  # Invalid: must be >= 0
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ServiceCreate(**data)
        
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_service_create_requires_deposit_without_amount(self):
        """Test service creation requiring deposit without amount."""
        data = {
            "business_id": 1,
            "name": "Haircut",
            "duration_minutes": 30,
            "price": Decimal("25.00"),
            "requires_deposit": True
            # Missing deposit_amount
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ServiceCreate(**data)
        
        assert "Deposit amount is required when requires_deposit is True" in str(exc_info.value)

    def test_service_update_partial(self):
        """Test partial service update."""
        data = {
            "name": "Premium Haircut",
            "price": Decimal("35.00")
        }
        
        service_update = ServiceUpdate(**data)
        assert service_update.name == "Premium Haircut"
        assert service_update.price == Decimal("35.00")
        assert service_update.duration_minutes is None  # Not provided


class TestServiceAddonSchemas:
    """Test service add-on schemas."""

    def test_service_addon_create_valid(self):
        """Test valid service add-on creation."""
        data = {
            "business_id": 1,
            "service_id": 1,
            "name": "Hair Wash",
            "description": "Shampoo and conditioning",
            "extra_duration_minutes": 15,
            "price": Decimal("5.00"),
            "is_active": True,
            "is_required": False,
            "max_quantity": 2,
            "sort_order": 1
        }
        
        addon = ServiceAddonCreate(**data)
        assert addon.name == "Hair Wash"
        assert addon.extra_duration_minutes == 15
        assert addon.max_quantity == 2

    def test_service_addon_create_negative_duration(self):
        """Test service add-on creation with negative duration."""
        data = {
            "business_id": 1,
            "service_id": 1,
            "name": "Hair Wash",
            "extra_duration_minutes": -5,  # Invalid: must be >= 0
            "price": Decimal("5.00")
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ServiceAddonCreate(**data)
        
        assert "Input should be greater than or equal to 0" in str(exc_info.value)

    def test_service_addon_create_zero_max_quantity(self):
        """Test service add-on creation with zero max quantity."""
        data = {
            "business_id": 1,
            "service_id": 1,
            "name": "Hair Wash",
            "price": Decimal("5.00"),
            "max_quantity": 0  # Invalid: must be > 0
        }
        
        with pytest.raises(ValidationError) as exc_info:
            ServiceAddonCreate(**data)
        
        assert "Input should be greater than 0" in str(exc_info.value)


class TestStaffServiceSchemas:
    """Test staff-service mapping schemas."""

    def test_staff_service_create_valid(self):
        """Test valid staff-service mapping creation."""
        data = {
            "staff_id": 1,
            "service_id": 1,
            "override_duration_minutes": 35,
            "override_price": Decimal("30.00"),
            "override_buffer_before_minutes": 7,
            "override_buffer_after_minutes": 8,
            "is_available": True,
            "expertise_level": "senior",
            "notes": "Specializes in modern cuts",
            "requires_approval": False
        }
        
        mapping = StaffServiceCreate(**data)
        assert mapping.staff_id == 1
        assert mapping.service_id == 1
        assert mapping.override_duration_minutes == 35
        assert mapping.expertise_level == "senior"

    def test_staff_service_create_invalid_override_duration(self):
        """Test staff-service mapping creation with invalid override duration."""
        data = {
            "staff_id": 1,
            "service_id": 1,
            "override_duration_minutes": 0  # Invalid: must be > 0 if provided
        }
        
        with pytest.raises(ValidationError) as exc_info:
            StaffServiceCreate(**data)
        
        assert "Input should be greater than 0" in str(exc_info.value)

    def test_staff_service_update_partial(self):
        """Test partial staff-service mapping update."""
        data = {
            "expertise_level": "expert",
            "notes": "Updated specialization"
        }
        
        mapping_update = StaffServiceUpdate(**data)
        assert mapping_update.expertise_level == "expert"
        assert mapping_update.notes == "Updated specialization"
        assert mapping_update.override_duration_minutes is None  # Not provided