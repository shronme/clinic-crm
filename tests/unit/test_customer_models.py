"""Unit tests for Customer model."""

import pytest
from datetime import date, datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer, CustomerStatus, GenderType
from app.models.business import Business


class TestCustomerModel:
    """Test Customer model functionality."""

    @pytest.fixture
    async def sample_business(self, db: AsyncSession):
        """Create a sample business for testing."""
        business = Business(name="Test Salon", timezone="UTC", currency="USD")
        db.add(business)
        await db.commit()
        await db.refresh(business)
        return business

    @pytest.fixture
    async def sample_customer(self, db: AsyncSession, sample_business: Business):
        """Create a sample customer for testing."""
        customer = Customer(
            business_id=sample_business.id,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+1-555-123-4567",
        )
        db.add(customer)
        await db.commit()
        await db.refresh(customer)
        return customer

    async def test_customer_creation(self, db: AsyncSession, sample_business: Business):
        """Test customer creation with required fields."""
        customer = Customer(
            business_id=sample_business.id,
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            phone="+1-555-987-6543",
            status=CustomerStatus.ACTIVE.value,
        )

        db.add(customer)
        await db.commit()
        await db.refresh(customer)

        assert customer.id is not None
        assert customer.uuid is not None
        assert customer.full_name == "Jane Smith"
        assert customer.display_phone == "+1-555-987-6543"
        assert customer.status == CustomerStatus.ACTIVE.value
        assert customer.total_visits == 0
        assert customer.total_spent == 0
        assert customer.source == "manual"

    async def test_customer_full_name_property(self, sample_customer: Customer):
        """Test full_name property."""
        assert sample_customer.full_name == "John Doe"

        # Test with only first name
        sample_customer.last_name = ""
        assert sample_customer.full_name == "John"

        # Test with only last name
        sample_customer.first_name = ""
        sample_customer.last_name = "Smith"
        assert sample_customer.full_name == "Smith"

    async def test_customer_display_phone_property(self, sample_customer: Customer):
        """Test display_phone property."""
        assert sample_customer.display_phone == "+1-555-123-4567"

        # Test with alternative phone when primary is None
        sample_customer.phone = None
        sample_customer.alternative_phone = "+1-555-999-8888"
        assert sample_customer.display_phone == "+1-555-999-8888"

        # Test with no phones
        sample_customer.alternative_phone = None
        assert sample_customer.display_phone == ""

    async def test_customer_age_property(self, sample_customer: Customer):
        """Test age calculation property."""
        # Test with no birth date
        assert sample_customer.age is None

        # Test with birth date
        sample_customer.date_of_birth = date(1990, 6, 15)
        age = sample_customer.age
        assert isinstance(age, int)
        assert age >= 30  # Assuming test runs in 2024 or later

    async def test_customer_lifetime_value_property(self, sample_customer: Customer):
        """Test lifetime_value property."""
        assert sample_customer.lifetime_value == 0.0

        # Test with spending
        sample_customer.total_spent = 12500  # $125.00 in cents
        assert sample_customer.lifetime_value == 125.0

    async def test_customer_is_new_customer_property(self, sample_customer: Customer):
        """Test is_new_customer property."""
        assert sample_customer.is_new_customer is True

        # Customer with 1 visit is still new
        sample_customer.total_visits = 1
        assert sample_customer.is_new_customer is True

        # Customer with 2+ visits is not new
        sample_customer.total_visits = 2
        assert sample_customer.is_new_customer is False

    async def test_customer_risk_level_property(self, sample_customer: Customer):
        """Test risk_level property."""
        # Low risk by default
        assert sample_customer.risk_level == "low"

        # High risk with many no-shows
        sample_customer.no_show_count = 3
        assert sample_customer.risk_level == "high"

        # Medium risk with some issues
        sample_customer.no_show_count = 1
        sample_customer.cancelled_appointment_count = 2
        assert sample_customer.risk_level == "medium"

        # Medium risk with many cancellations
        sample_customer.no_show_count = 0
        sample_customer.cancelled_appointment_count = 3
        assert sample_customer.risk_level == "medium"

    async def test_update_visit_stats(self, sample_customer: Customer):
        """Test update_visit_stats method."""
        visit_date = date(2024, 6, 15)
        amount_spent = 5000  # $50.00 in cents

        sample_customer.update_visit_stats(visit_date, amount_spent)

        assert sample_customer.first_visit_date == visit_date
        assert sample_customer.last_visit_date == visit_date
        assert sample_customer.total_visits == 1
        assert sample_customer.total_spent == 5000

        # Second visit
        second_visit = date(2024, 7, 20)
        sample_customer.update_visit_stats(second_visit, 7500)

        assert sample_customer.first_visit_date == visit_date  # Unchanged
        assert sample_customer.last_visit_date == second_visit
        assert sample_customer.total_visits == 2
        assert sample_customer.total_spent == 12500

    async def test_can_book_appointment(self, sample_customer: Customer):
        """Test can_book_appointment method."""
        # Active customer can book
        can_book, reason = sample_customer.can_book_appointment()
        assert can_book is True
        assert reason == ""

        # Blocked customer cannot book
        sample_customer.status = CustomerStatus.BLOCKED.value
        can_book, reason = sample_customer.can_book_appointment()
        assert can_book is False
        assert "blocked" in reason.lower()

        # Inactive customer cannot book
        sample_customer.status = CustomerStatus.INACTIVE.value
        can_book, reason = sample_customer.can_book_appointment()
        assert can_book is False
        assert "inactive" in reason.lower()

        # Customer with too many no-shows cannot book
        sample_customer.status = CustomerStatus.ACTIVE.value
        sample_customer.no_show_count = 5
        can_book, reason = sample_customer.can_book_appointment()
        assert can_book is False
        assert "no-show" in reason.lower()

    async def test_customer_relationships(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test customer relationships."""
        # Create referrer customer
        referrer = Customer(
            business_id=sample_business.id,
            first_name="Alice",
            last_name="Johnson",
            email="alice.j@example.com",
        )
        db.add(referrer)
        await db.commit()
        await db.refresh(referrer)

        # Create referred customer
        referred = Customer(
            business_id=sample_business.id,
            first_name="Bob",
            last_name="Wilson",
            email="bob.w@example.com",
            referred_by_customer_id=referrer.id,
        )
        db.add(referred)
        await db.commit()
        await db.refresh(referred)

        # Test relationships
        assert referred.referred_by_customer_id == referrer.id

    async def test_customer_status_enum(self, sample_customer: Customer):
        """Test customer status enum values."""
        # Test all status values
        sample_customer.status = CustomerStatus.ACTIVE.value
        assert sample_customer.status == "active"

        sample_customer.status = CustomerStatus.INACTIVE.value
        assert sample_customer.status == "inactive"

        sample_customer.status = CustomerStatus.BLOCKED.value
        assert sample_customer.status == "blocked"

    async def test_customer_gender_enum(self, sample_customer: Customer):
        """Test customer gender enum values."""
        # Test all gender values
        sample_customer.gender = GenderType.MALE.value
        assert sample_customer.gender == "male"

        sample_customer.gender = GenderType.FEMALE.value
        assert sample_customer.gender == "female"

        sample_customer.gender = GenderType.OTHER.value
        assert sample_customer.gender == "other"

        sample_customer.gender = GenderType.PREFER_NOT_TO_SAY.value
        assert sample_customer.gender == "prefer_not_to_say"

    async def test_customer_communication_preferences(self, sample_customer: Customer):
        """Test customer communication preferences defaults."""
        assert sample_customer.email_notifications is True
        assert sample_customer.sms_notifications is True
        assert sample_customer.marketing_emails is False
        assert sample_customer.marketing_sms is False

    async def test_customer_financial_tracking(self, sample_customer: Customer):
        """Test customer financial tracking fields."""
        assert sample_customer.total_spent == 0
        assert sample_customer.lifetime_value == 0.0

        # Update financial data
        sample_customer.total_spent = 25000  # $250.00
        assert sample_customer.lifetime_value == 250.0

    async def test_customer_behavioral_flags(self, sample_customer: Customer):
        """Test customer behavioral tracking flags."""
        assert sample_customer.is_no_show_risk is False
        assert sample_customer.no_show_count == 0
        assert sample_customer.cancelled_appointment_count == 0
        assert sample_customer.is_vip is False

    async def test_customer_data_source_tracking(self, sample_customer: Customer):
        """Test customer data source tracking."""
        assert sample_customer.source == "manual"
        assert sample_customer.external_id is None

        # Test CSV import source
        csv_customer = Customer(
            business_id=sample_customer.business_id,
            first_name="Import",
            last_name="Test",
            source="csv_import",
            external_id="EXT_123",
        )

        assert csv_customer.source == "csv_import"
        assert csv_customer.external_id == "EXT_123"

    async def test_customer_repr(self, sample_customer: Customer):
        """Test customer string representation."""
        repr_str = repr(sample_customer)
        assert "Customer" in repr_str
        assert "John Doe" in repr_str
        assert sample_customer.email in repr_str
        assert sample_customer.phone in repr_str
