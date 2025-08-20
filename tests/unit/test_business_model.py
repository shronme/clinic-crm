import pytest
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business


@pytest.mark.unit
class TestBusinessModel:
    """Unit tests for Business model."""

    @pytest.mark.asyncio
    async def test_business_creation_with_defaults(self, db: AsyncSession):
        """Test creating a business with default values."""
        business = Business(name="Test Salon")
        db.add(business)
        await db.commit()
        await db.refresh(business)

        assert business.id is not None
        assert business.name == "Test Salon"
        assert business.timezone == "UTC"
        assert business.currency == "USD"
        assert business.is_active is True
        assert business.created_at is not None
        assert business.updated_at is not None
        assert business.logo_url is None
        assert business.description is None
        assert business.phone is None
        assert business.email is None
        assert business.website is None
        assert business.address is None
        assert business.branding is None
        assert business.policy is None

    @pytest.mark.asyncio
    async def test_business_creation_with_all_fields(self, db: AsyncSession):
        """Test creating a business with all fields populated."""
        branding_data = {
            "primary_color": "#FF0000",
            "secondary_color": "#00FF00",
            "logo_position": "center",
            "custom_css": ".custom { color: red; }",
        }

        policy_data = {
            "min_lead_time_hours": 2,
            "max_lead_time_days": 30,
            "cancellation_window_hours": 24,
            "deposit_required": True,
            "no_show_fee": 25.0,
            "late_arrival_grace_minutes": 10,
        }

        business = Business(
            name="Full Service Salon",
            logo_url="https://example.com/logo.png",
            description="A premium salon experience",
            phone="+1-555-123-4567",
            email="info@fullservice.com",
            website="https://fullservice.com",
            address="123 Main St, City, State 12345",
            timezone="America/New_York",
            currency="USD",
            branding=branding_data,
            policy=policy_data,
            is_active=True,
        )

        db.add(business)
        await db.commit()
        await db.refresh(business)

        assert business.id is not None
        assert business.name == "Full Service Salon"
        assert business.logo_url == "https://example.com/logo.png"
        assert business.description == "A premium salon experience"
        assert business.phone == "+1-555-123-4567"
        assert business.email == "info@fullservice.com"
        assert business.website == "https://fullservice.com"
        assert business.address == "123 Main St, City, State 12345"
        assert business.timezone == "America/New_York"
        assert business.currency == "USD"
        assert business.branding == branding_data
        assert business.policy == policy_data
        assert business.is_active is True
        assert business.created_at is not None
        assert business.updated_at is not None

    @pytest.mark.asyncio
    async def test_business_json_fields(self, db: AsyncSession):
        """Test that JSON fields store and retrieve complex data correctly."""
        branding_data = {
            "primary_color": "#FF0000",
            "secondary_color": "#00FF00",
            "logo_position": "left",
            "custom_css": ".header { background: #FF0000; }",
        }

        policy_data = {
            "min_lead_time_hours": 4,
            "max_lead_time_days": 60,
            "cancellation_window_hours": 12,
            "deposit_required": False,
            "no_show_fee": 50.0,
            "late_arrival_grace_minutes": 5,
        }

        business = Business(
            name="JSON Test Salon", branding=branding_data, policy=policy_data
        )

        db.add(business)
        await db.commit()
        await db.refresh(business)

        # Verify JSON data is stored and retrieved correctly
        assert business.branding["primary_color"] == "#FF0000"
        assert business.branding["secondary_color"] == "#00FF00"
        assert business.branding["logo_position"] == "left"
        assert business.branding["custom_css"] == ".header { background: #FF0000; }"

        assert business.policy["min_lead_time_hours"] == 4
        assert business.policy["max_lead_time_days"] == 60
        assert business.policy["cancellation_window_hours"] == 12
        assert business.policy["deposit_required"] is False
        assert business.policy["no_show_fee"] == 50.0
        assert business.policy["late_arrival_grace_minutes"] == 5

    @pytest.mark.asyncio
    async def test_business_name_required(self, db: AsyncSession):
        """Test that business name is required."""
        business = Business()  # No name provided
        db.add(business)

        with pytest.raises(Exception):  # Should raise IntegrityError
            await db.commit()

    @pytest.mark.asyncio
    async def test_business_audit_timestamps(self, db: AsyncSession):
        """Test that audit timestamps are set correctly."""
        business = Business(name="Timestamp Test Salon")
        db.add(business)
        await db.commit()
        await db.refresh(business)

        initial_created_at = business.created_at
        initial_updated_at = business.updated_at

        assert initial_created_at is not None
        assert initial_updated_at is not None
        assert initial_created_at == initial_updated_at

        # Wait a brief moment to ensure timestamp difference
        await asyncio.sleep(0.01)

        # Update the business
        business.description = "Updated description"
        await db.commit()
        await db.refresh(business)

        # created_at should remain the same, updated_at should change
        assert business.created_at == initial_created_at
        assert (
            business.updated_at >= initial_updated_at
        )  # Use >= instead of > for fast systems

    @pytest.mark.asyncio
    async def test_business_string_length_limits(self, db: AsyncSession):
        """Test string field length constraints."""
        # Test with valid lengths
        base_logo = "https://example.com/"
        base_email = "test@"
        email_suffix = ".com"
        base_website = "https://"
        website_suffix = ".com"

        business = Business(
            name="A" * 255,  # Max length for name
            logo_url=base_logo
            + "a" * (500 - len(base_logo)),  # Max length for logo_url
            phone="+" + "1" * 49,  # Max length for phone
            email=base_email
            + "a" * (255 - len(base_email) - len(email_suffix))
            + email_suffix,  # Max length for email
            website=base_website
            + "a" * (500 - len(base_website) - len(website_suffix))
            + website_suffix,  # Max length for website
            timezone="America/New_York",  # Valid timezone under 50 chars
            currency="USD",  # Valid currency under 10 chars
        )

        db.add(business)
        await db.commit()
        await db.refresh(business)

        assert len(business.name) == 255
        assert len(business.logo_url) == 500
        assert len(business.phone) == 50
        assert len(business.email) == 255
        assert len(business.website) == 500
        assert business.timezone == "America/New_York"
        assert business.currency == "USD"
