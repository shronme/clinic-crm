import pytest
import uuid
from datetime import datetime
from pydantic import ValidationError

from app.schemas.business import (
    BusinessCreate,
    BusinessUpdate,
    BusinessResponse,
    BusinessBranding,
    BusinessPolicy,
    validate_timezone,
    validate_currency,
)


@pytest.mark.unit
class TestBusinessSchemas:
    """Unit tests for Business schemas."""

    def test_business_branding_schema(self):
        """Test BusinessBranding schema validation."""
        branding = BusinessBranding(
            primary_color="#FF0000",
            secondary_color="#00FF00",
            logo_position="center",
            custom_css=".header { color: red; }",
        )

        assert branding.primary_color == "#FF0000"
        assert branding.secondary_color == "#00FF00"
        assert branding.logo_position == "center"
        assert branding.custom_css == ".header { color: red; }"

    def test_business_branding_schema_defaults(self):
        """Test BusinessBranding schema with default values."""
        branding = BusinessBranding()

        assert branding.primary_color is None
        assert branding.secondary_color is None
        assert branding.logo_position == "center"
        assert branding.custom_css is None

    def test_business_policy_schema(self):
        """Test BusinessPolicy schema validation."""
        policy = BusinessPolicy(
            min_lead_time_hours=2,
            max_lead_time_days=30,
            cancellation_window_hours=24,
            deposit_required=True,
            no_show_fee=25.0,
            late_arrival_grace_minutes=10,
        )

        assert policy.min_lead_time_hours == 2
        assert policy.max_lead_time_days == 30
        assert policy.cancellation_window_hours == 24
        assert policy.deposit_required is True
        assert policy.no_show_fee == 25.0
        assert policy.late_arrival_grace_minutes == 10

    def test_business_policy_schema_defaults(self):
        """Test BusinessPolicy schema with default values."""
        policy = BusinessPolicy()

        assert policy.min_lead_time_hours == 1
        assert policy.max_lead_time_days == 90
        assert policy.cancellation_window_hours == 6
        assert policy.deposit_required is False
        assert policy.no_show_fee is None
        assert policy.late_arrival_grace_minutes == 15

    def test_business_policy_schema_validation_errors(self):
        """Test BusinessPolicy schema validation constraints."""
        # Test negative values
        with pytest.raises(ValidationError):
            BusinessPolicy(min_lead_time_hours=-1)

        with pytest.raises(ValidationError):
            BusinessPolicy(max_lead_time_days=0)

        with pytest.raises(ValidationError):
            BusinessPolicy(cancellation_window_hours=-5)

        with pytest.raises(ValidationError):
            BusinessPolicy(no_show_fee=-10.0)

        with pytest.raises(ValidationError):
            BusinessPolicy(late_arrival_grace_minutes=-1)

    def test_business_create_schema_minimal(self):
        """Test BusinessCreate schema with minimal required fields."""
        business = BusinessCreate(name="Test Salon")

        assert business.name == "Test Salon"
        assert business.timezone == "UTC"
        assert business.currency == "USD"
        assert business.logo_url is None
        assert business.description is None
        assert business.phone is None
        assert business.email is None
        assert business.website is None
        assert business.address is None
        assert business.branding is None
        assert business.policy is None

    def test_business_create_schema_full(self):
        """Test BusinessCreate schema with all fields."""
        branding = BusinessBranding(primary_color="#FF0000")
        policy = BusinessPolicy(min_lead_time_hours=4)

        business = BusinessCreate(
            name="Full Service Salon",
            logo_url="https://example.com/logo.png",
            description="A premium salon",
            phone="+1-555-123-4567",
            email="info@salon.com",
            website="https://salon.com",
            address="123 Main St",
            timezone="America/New_York",
            currency="EUR",
            branding=branding,
            policy=policy,
        )

        assert business.name == "Full Service Salon"
        assert business.logo_url == "https://example.com/logo.png"
        assert business.description == "A premium salon"
        assert business.phone == "+1-555-123-4567"
        assert business.email == "info@salon.com"
        assert business.website == "https://salon.com"
        assert business.address == "123 Main St"
        assert business.timezone == "America/New_York"
        assert business.currency == "EUR"
        assert business.branding == branding
        assert business.policy == policy

    def test_business_create_schema_validation_errors(self):
        """Test BusinessCreate schema validation constraints."""
        # Test empty name
        with pytest.raises(ValidationError):
            BusinessCreate(name="")

        # Test name too long
        with pytest.raises(ValidationError):
            BusinessCreate(name="a" * 256)

        # Test invalid timezone
        with pytest.raises(ValidationError):
            BusinessCreate(name="Test", timezone="Invalid/Timezone")

        # Test invalid currency
        with pytest.raises(ValidationError):
            BusinessCreate(name="Test", currency="INVALID")

    def test_business_update_schema_empty(self):
        """Test BusinessUpdate schema with no fields set."""
        update = BusinessUpdate()

        assert update.name is None
        assert update.logo_url is None
        assert update.description is None
        assert update.phone is None
        assert update.email is None
        assert update.website is None
        assert update.address is None
        assert update.timezone is None
        assert update.currency is None
        assert update.branding is None
        assert update.policy is None
        assert update.is_active is None

    def test_business_update_schema_partial(self):
        """Test BusinessUpdate schema with partial updates."""
        update = BusinessUpdate(
            name="Updated Name", description="Updated description", is_active=False
        )

        assert update.name == "Updated Name"
        assert update.description == "Updated description"
        assert update.is_active is False
        assert update.logo_url is None
        assert update.timezone is None

    def test_business_update_schema_validation_errors(self):
        """Test BusinessUpdate schema validation constraints."""
        # Test empty name when provided
        with pytest.raises(ValidationError):
            BusinessUpdate(name="")

        # Test invalid timezone when provided
        with pytest.raises(ValidationError):
            BusinessUpdate(timezone="Invalid/Timezone")

        # Test invalid currency when provided
        with pytest.raises(ValidationError):
            BusinessUpdate(currency="INVALID")

    def test_business_response_schema(self):
        """Test BusinessResponse schema."""
        now = datetime.now()
        test_uuid = uuid.uuid4()

        response = BusinessResponse(
            id=1,
            uuid=test_uuid,
            name="Test Salon",
            timezone="UTC",
            currency="USD",
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        assert response.id == 1
        assert response.uuid == test_uuid
        assert response.name == "Test Salon"
        assert response.timezone == "UTC"
        assert response.currency == "USD"
        assert response.is_active is True
        assert response.created_at == now
        assert response.updated_at == now

    def test_validate_timezone_function_valid(self):
        """Test validate_timezone function with valid timezones."""
        valid_timezones = [
            "UTC",
            "America/New_York",
            "Europe/London",
            "Asia/Tokyo",
            "Australia/Sydney",
        ]

        for tz in valid_timezones:
            result = validate_timezone(tz)
            assert result == tz

    def test_validate_timezone_function_invalid(self):
        """Test validate_timezone function with invalid timezones."""
        invalid_timezones = [
            "Invalid/Timezone",
            "Not/A/Real/Timezone",
            "PST",  # Deprecated, actually invalid
            "XYZ/ABC",  # Completely invalid
            "",
        ]

        for tz in invalid_timezones:
            with pytest.raises(ValueError, match=f"Invalid timezone: {tz}"):
                validate_timezone(tz)

    def test_validate_currency_function_valid(self):
        """Test validate_currency function with valid currencies."""
        valid_currencies = [
            "USD",
            "EUR",
            "GBP",
            "CAD",
            "AUD",
            "JPY",
            "CHF",
            "CNY",
            "INR",
        ]

        for currency in valid_currencies:
            result = validate_currency(currency)
            assert result == currency

    def test_validate_currency_function_invalid(self):
        """Test validate_currency function with invalid currencies."""
        invalid_currencies = ["XXX", "INVALID", "BTC", ""]

        for currency in invalid_currencies:
            with pytest.raises(ValueError, match=f"Unsupported currency: {currency}"):
                validate_currency(currency)

    def test_business_create_field_length_limits(self):
        """Test BusinessCreate schema field length constraints."""
        # Test maximum allowed lengths
        business = BusinessCreate(
            name="a" * 255,
            logo_url="a" * 500,  # Exactly 500 chars
            phone="a" * 50,  # Exactly 50 chars
            email="a" * 255,  # Exactly 255 chars
            website="a" * 500,  # Exactly 500 chars
            timezone="America/New_York",
            currency="USD",
        )

        assert len(business.name) == 255
        assert len(business.logo_url) == 500
        assert len(business.phone) == 50
        assert len(business.email) == 255
        assert len(business.website) == 500

        # Test exceeding length limits
        with pytest.raises(ValidationError):
            BusinessCreate(name="a" * 256)

        with pytest.raises(ValidationError):
            BusinessCreate(name="Test", logo_url="a" * 501)

        with pytest.raises(ValidationError):
            BusinessCreate(name="Test", phone="a" * 51)

    def test_business_update_field_length_limits(self):
        """Test BusinessUpdate schema field length constraints."""
        # Test maximum allowed lengths
        update = BusinessUpdate(
            name="a" * 255,
            logo_url="a" * 500,  # Exactly 500 chars
            phone="a" * 50,  # Exactly 50 chars
            email="a" * 255,  # Exactly 255 chars
            website="a" * 500,  # Exactly 500 chars
            timezone="America/New_York",
            currency="USD",
        )

        assert len(update.name) == 255
        assert len(update.logo_url) == 500
        assert len(update.phone) == 50
        assert len(update.email) == 255
        assert len(update.website) == 500

        # Test exceeding length limits
        with pytest.raises(ValidationError):
            BusinessUpdate(name="a" * 256)

        with pytest.raises(ValidationError):
            BusinessUpdate(logo_url="a" * 501)

        with pytest.raises(ValidationError):
            BusinessUpdate(phone="a" * 51)
