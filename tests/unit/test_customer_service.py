"""Unit tests for Customer service layer."""

import base64
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.customer import Customer, CustomerStatus
from app.schemas.customer import (
    CustomerCreate,
    CustomerCSVImport,
    CustomerSearch,
    CustomerUpdate,
)
from app.services.customer import customer_service


class TestCustomerService:
    """Test Customer service functionality."""

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
            status=CustomerStatus.ACTIVE.value,
        )
        db.add(customer)
        await db.commit()
        await db.refresh(customer)
        return customer

    async def test_create_customer(self, db: AsyncSession, sample_business: Business):
        """Test creating a new customer."""
        customer_data = CustomerCreate(
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            phone="+1-555-987-6543",
            status=CustomerStatus.ACTIVE,
            city="New York",
            state="NY",
        )

        customer = await customer_service.create_customer(
            db, customer_data, sample_business.id
        )

        assert customer.id is not None
        assert customer.uuid is not None
        assert customer.business_id == sample_business.id
        assert customer.first_name == "Jane"
        assert customer.last_name == "Smith"
        assert customer.email == "jane.smith@example.com"
        assert customer.status == CustomerStatus.ACTIVE.value
        assert customer.city == "New York"
        assert customer.state == "NY"

    async def test_create_customer_duplicate_email(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test creating customer with duplicate email raises error."""
        customer_data = CustomerCreate(
            first_name="First", last_name="Customer", email="duplicate@example.com"
        )

        # Create first customer
        await customer_service.create_customer(db, customer_data, sample_business.id)

        # Attempt to create second customer with same email should fail
        duplicate_data = CustomerCreate(
            first_name="Second", last_name="Customer", email="duplicate@example.com"
        )

        with pytest.raises(ValueError, match="email"):
            await customer_service.create_customer(
                db, duplicate_data, sample_business.id
            )

    async def test_get_customer_by_uuid(
        self,
        db: AsyncSession,
        sample_customer: Customer,
        sample_business: Business,
    ):
        """Test retrieving customer by UUID."""
        found_customer = await customer_service.get_customer_by_uuid(
            db, sample_customer.uuid, sample_business.id
        )

        assert found_customer is not None
        assert found_customer.id == sample_customer.id
        assert found_customer.email == sample_customer.email

    async def test_get_customer_by_uuid_not_found(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test retrieving non-existent customer returns None."""
        from uuid import uuid4

        found_customer = await customer_service.get_customer_by_uuid(
            db, uuid4(), sample_business.id
        )

        assert found_customer is None

    async def test_get_customers(self, db: AsyncSession, sample_business: Business):
        """Test retrieving customers with pagination."""
        # Create multiple customers
        customers_data = [
            {
                "first_name": "Alice",
                "last_name": "Johnson",
                "email": "alice@example.com",
            },
            {"first_name": "Bob", "last_name": "Wilson", "email": "bob@example.com"},
            {
                "first_name": "Charlie",
                "last_name": "Brown",
                "email": "charlie@example.com",
            },
        ]

        for data in customers_data:
            customer = Customer(business_id=sample_business.id, **data)
            db.add(customer)

        await db.commit()

        # Test pagination
        customers = await customer_service.get_customers(
            db, sample_business.id, skip=0, limit=2
        )

        assert len(customers) == 2

        # Test with different pagination
        customers_page2 = await customer_service.get_customers(
            db, sample_business.id, skip=2, limit=2
        )

        assert len(customers_page2) == 1

    async def test_update_customer(
        self,
        db: AsyncSession,
        sample_customer: Customer,
        sample_business: Business,
    ):
        """Test updating customer information."""
        update_data = CustomerUpdate(
            first_name="Updated", phone="+1-555-999-8888", city="Boston", is_vip=True
        )

        updated_customer = await customer_service.update_customer(
            db, sample_customer.uuid, update_data, sample_business.id
        )

        assert updated_customer is not None
        assert updated_customer.first_name == "Updated"
        assert updated_customer.phone == "+1-555-999-8888"
        assert updated_customer.city == "Boston"
        assert updated_customer.is_vip is True
        # Unchanged fields should remain the same
        assert updated_customer.last_name == sample_customer.last_name
        assert updated_customer.email == sample_customer.email

    async def test_delete_customer_soft(
        self,
        db: AsyncSession,
        sample_customer: Customer,
        sample_business: Business,
    ):
        """Test soft deleting customer."""
        result = await customer_service.delete_customer(
            db, sample_customer.uuid, sample_business.id, soft_delete=True
        )

        assert result is True

        # Verify customer is marked inactive
        updated_customer = await customer_service.get_customer_by_uuid(
            db, sample_customer.uuid, sample_business.id
        )
        assert updated_customer.status == CustomerStatus.INACTIVE.value

    async def test_search_customers_by_name(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test searching customers by name."""
        # Create test customers
        customers_data = [
            {
                "first_name": "John",
                "last_name": "Smith",
                "email": "john.smith@example.com",
            },
            {
                "first_name": "Jane",
                "last_name": "Johnson",
                "email": "jane.johnson@example.com",
            },
            {
                "first_name": "Bob",
                "last_name": "Williams",
                "email": "bob.williams@example.com",
            },
        ]

        for data in customers_data:
            customer = Customer(business_id=sample_business.id, **data)
            db.add(customer)

        await db.commit()

        # Search by first name
        search_params = CustomerSearch(query="John")
        customers, total = await customer_service.search_customers(
            db, sample_business.id, search_params
        )

        assert total >= 1
        assert any(customer.first_name == "John" for customer in customers)

    async def test_search_customers_by_email(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test searching customers by email."""
        customer = Customer(
            business_id=sample_business.id,
            first_name="Test",
            last_name="User",
            email="test.user@example.com",
        )
        db.add(customer)
        await db.commit()

        # Search by email
        search_params = CustomerSearch(query="test.user@example.com")
        customers, total = await customer_service.search_customers(
            db, sample_business.id, search_params
        )

        assert total >= 1
        assert any(customer.email == "test.user@example.com" for customer in customers)

    async def test_search_customers_by_status(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test searching customers by status."""
        # Create customers with different statuses
        active_customer = Customer(
            business_id=sample_business.id,
            first_name="Active",
            last_name="Customer",
            status=CustomerStatus.ACTIVE.value,
        )
        inactive_customer = Customer(
            business_id=sample_business.id,
            first_name="Inactive",
            last_name="Customer",
            status=CustomerStatus.INACTIVE.value,
        )

        db.add(active_customer)
        db.add(inactive_customer)
        await db.commit()

        # Search for active customers
        search_params = CustomerSearch(status=CustomerStatus.ACTIVE)
        customers, total = await customer_service.search_customers(
            db, sample_business.id, search_params
        )

        assert all(
            customer.status == CustomerStatus.ACTIVE.value for customer in customers
        )

    async def test_search_customers_by_vip_status(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test searching customers by VIP status."""
        vip_customer = Customer(
            business_id=sample_business.id,
            first_name="VIP",
            last_name="Customer",
            is_vip=True,
        )
        regular_customer = Customer(
            business_id=sample_business.id,
            first_name="Regular",
            last_name="Customer",
            is_vip=False,
        )

        db.add(vip_customer)
        db.add(regular_customer)
        await db.commit()

        # Search for VIP customers
        search_params = CustomerSearch(is_vip=True)
        customers, total = await customer_service.search_customers(
            db, sample_business.id, search_params
        )

        assert all(customer.is_vip is True for customer in customers)

    async def test_get_customer_stats(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test getting customer statistics."""
        # Create customers with different statuses and attributes
        customers_data = [
            {
                "first_name": "Active1",
                "last_name": "User",
                "status": CustomerStatus.ACTIVE.value,
            },
            {
                "first_name": "Active2",
                "last_name": "User",
                "status": CustomerStatus.ACTIVE.value,
                "is_vip": True,
            },
            {
                "first_name": "Inactive",
                "last_name": "User",
                "status": CustomerStatus.INACTIVE.value,
            },
            {
                "first_name": "Blocked",
                "last_name": "User",
                "status": CustomerStatus.BLOCKED.value,
            },
            {"first_name": "HighRisk", "last_name": "User", "no_show_count": 3},
        ]

        for data in customers_data:
            customer = Customer(business_id=sample_business.id, **data)
            db.add(customer)

        await db.commit()

        stats = await customer_service.get_customer_stats(db, sample_business.id)

        assert stats.total_customers >= 5
        assert stats.active_customers >= 2
        assert stats.inactive_customers >= 1
        assert stats.blocked_customers >= 1
        assert stats.vip_customers >= 1
        assert stats.high_risk_customers >= 1

    async def test_import_customers_from_csv(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test importing customers from CSV."""
        # Create sample CSV data
        csv_data = """first_name,last_name,email,phone
John,Doe,john.doe@example.com,555-1234
Jane,Smith,jane.smith@example.com,555-5678
"""

        csv_base64 = base64.b64encode(csv_data.encode()).decode()

        import_data = CustomerCSVImport(
            file_data=csv_base64,
            mapping={
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "email",
                "phone": "phone",
            },
            skip_duplicates=True,
            update_existing=False,
        )

        result = await customer_service.import_customers_from_csv(
            db, sample_business.id, import_data
        )

        assert result.total_records == 2
        assert result.imported_records == 2
        assert result.failed_records == 0
        assert len(result.errors) == 0

    async def test_import_customers_csv_with_duplicates(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test CSV import with duplicate handling."""
        # Create existing customer
        existing_customer = Customer(
            business_id=sample_business.id,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
        )
        db.add(existing_customer)
        await db.commit()

        # CSV with duplicate email
        csv_data = """first_name,last_name,email
John,Updated,john.doe@example.com
Jane,Smith,jane.smith@example.com
"""

        csv_base64 = base64.b64encode(csv_data.encode()).decode()

        # Test skip duplicates
        import_data = CustomerCSVImport(
            file_data=csv_base64,
            mapping={
                "first_name": "first_name",
                "last_name": "last_name",
                "email": "email",
            },
            skip_duplicates=True,
            update_existing=False,
        )

        result = await customer_service.import_customers_from_csv(
            db, sample_business.id, import_data
        )

        assert result.total_records == 2
        assert result.imported_records == 1  # Only new customer
        assert len(result.warnings) >= 1  # Warning about skipped duplicate

    async def test_update_customer_visit_stats(
        self, db: AsyncSession, sample_customer: Customer
    ):
        """Test updating customer visit statistics."""
        visit_date = date(2024, 6, 15)
        amount_spent = 5000  # $50.00 in cents

        await customer_service.update_customer_visit_stats(
            db, sample_customer.id, visit_date, amount_spent
        )

        # Refresh customer from database
        await db.refresh(sample_customer)

        assert sample_customer.first_visit_date == visit_date
        assert sample_customer.last_visit_date == visit_date
        assert sample_customer.total_visits == 1
        assert sample_customer.total_spent == 5000

    async def test_get_customer_appointment_history_empty(
        self,
        db: AsyncSession,
        sample_customer: Customer,
        sample_business: Business,
    ):
        """Test getting customer appointment history when empty."""
        appointments = await customer_service.get_customer_appointment_history(
            db, sample_customer.uuid, sample_business.id
        )

        assert appointments == []

    async def test_search_customers_pagination(
        self, db: AsyncSession, sample_business: Business
    ):
        """Test customer search with pagination."""
        # Create multiple customers
        for i in range(5):
            customer = Customer(
                business_id=sample_business.id,
                first_name=f"Customer{i}",
                last_name="Test",
                email=f"customer{i}@example.com",
            )
            db.add(customer)

        await db.commit()

        # Test first page
        search_params = CustomerSearch()
        customers_page1, total = await customer_service.search_customers(
            db, sample_business.id, search_params, skip=0, limit=3
        )

        assert len(customers_page1) == 3
        assert total >= 5

        # Test second page
        customers_page2, total = await customer_service.search_customers(
            db, sample_business.id, search_params, skip=3, limit=3
        )

        assert len(customers_page2) >= 2
        assert total >= 5
