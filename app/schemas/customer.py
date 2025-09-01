from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class CustomerStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class GenderType(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class CustomerPreferences(BaseModel):
    """Customer preferences model."""

    email_notifications: bool = Field(
        default=True, description="Receive email notifications"
    )
    sms_notifications: bool = Field(
        default=True, description="Receive SMS notifications"
    )
    marketing_emails: bool = Field(
        default=False, description="Receive marketing emails"
    )
    marketing_sms: bool = Field(default=False, description="Receive marketing SMS")


class CustomerEmergencyContact(BaseModel):
    """Customer emergency contact information."""

    name: Optional[str] = Field(
        None, max_length=200, description="Emergency contact name"
    )
    phone: Optional[str] = Field(
        None, max_length=20, description="Emergency contact phone"
    )
    relationship: Optional[str] = Field(
        None, max_length=50, description="Relationship to customer"
    )


class CustomerBase(BaseModel):
    """Base customer schema with common fields."""

    first_name: str = Field(
        ..., min_length=1, max_length=100, description="Customer first name"
    )
    last_name: str = Field(
        ..., min_length=1, max_length=100, description="Customer last name"
    )
    email: Optional[EmailStr] = Field(None, description="Customer email address")
    phone: Optional[str] = Field(
        None, max_length=20, description="Primary phone number"
    )
    alternative_phone: Optional[str] = Field(
        None, max_length=20, description="Alternative phone number"
    )

    # Address information
    address: Optional[str] = Field(None, description="Street address")
    city: Optional[str] = Field(None, max_length=100, description="City")
    state: Optional[str] = Field(None, max_length=50, description="State/Province")
    postal_code: Optional[str] = Field(
        None, max_length=20, description="Postal/ZIP code"
    )
    country: Optional[str] = Field("US", max_length=50, description="Country code")

    # Personal details
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    gender: Optional[GenderType] = Field(None, description="Gender")
    occupation: Optional[str] = Field(None, max_length=100, description="Occupation")

    # Customer notes and preferences
    preferences: Optional[str] = Field(None, description="General preferences")
    allergies: Optional[str] = Field(None, description="Hair/skin allergies")
    notes: Optional[str] = Field(None, description="Staff notes about customer")

    # Communication preferences
    email_notifications: bool = Field(
        default=True, description="Email notification preference"
    )
    sms_notifications: bool = Field(
        default=True, description="SMS notification preference"
    )
    marketing_emails: bool = Field(
        default=False, description="Marketing email preference"
    )
    marketing_sms: bool = Field(default=False, description="Marketing SMS preference")

    # Customer status
    status: CustomerStatus = Field(
        default=CustomerStatus.ACTIVE, description="Customer status"
    )
    is_vip: bool = Field(default=False, description="VIP customer flag")
    referral_source: Optional[str] = Field(
        None, max_length=100, description="How customer found business"
    )

    # Emergency contact
    emergency_contact_name: Optional[str] = Field(
        None, max_length=200, description="Emergency contact name"
    )
    emergency_contact_phone: Optional[str] = Field(
        None, max_length=20, description="Emergency contact phone"
    )
    emergency_contact_relationship: Optional[str] = Field(
        None, max_length=50, description="Emergency contact relationship"
    )

    # Social media
    instagram_handle: Optional[str] = Field(
        None, max_length=100, description="Instagram handle"
    )
    facebook_profile: Optional[str] = Field(
        None, max_length=255, description="Facebook profile URL"
    )

    @field_validator("phone", "alternative_phone", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, v):
        if (
            v
            and not v.replace("+", "")
            .replace("-", "")
            .replace(" ", "")
            .replace("(", "")
            .replace(")", "")
            .isdigit()
        ):
            raise ValueError(
                "Phone number must contain only digits, spaces, dashes, plus signs, "
                "and parentheses"
            )
        return v


class CustomerCreate(CustomerBase):
    """Schema for creating a new customer."""

    business_id: Optional[int] = Field(
        None, description="Business ID (set by dependency injection)"
    )
    source: str = Field(default="manual", description="Data source")
    external_id: Optional[str] = Field(
        None, max_length=100, description="External system ID"
    )


class CustomerUpdate(BaseModel):
    """Schema for updating customer information."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    alternative_phone: Optional[str] = Field(None, max_length=20)

    # Address information
    address: Optional[str] = None
    city: Optional[str] = Field(None, max_length=100)
    state: Optional[str] = Field(None, max_length=50)
    postal_code: Optional[str] = Field(None, max_length=20)
    country: Optional[str] = Field(None, max_length=50)

    # Personal details
    date_of_birth: Optional[date] = None
    gender: Optional[GenderType] = None
    occupation: Optional[str] = Field(None, max_length=100)

    # Customer notes and preferences
    preferences: Optional[str] = None
    allergies: Optional[str] = None
    notes: Optional[str] = None

    # Communication preferences
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    marketing_emails: Optional[bool] = None
    marketing_sms: Optional[bool] = None

    # Customer status
    status: Optional[CustomerStatus] = None
    is_vip: Optional[bool] = None
    referral_source: Optional[str] = Field(None, max_length=100)

    # Emergency contact
    emergency_contact_name: Optional[str] = Field(None, max_length=200)
    emergency_contact_phone: Optional[str] = Field(None, max_length=20)
    emergency_contact_relationship: Optional[str] = Field(None, max_length=50)

    # Social media
    instagram_handle: Optional[str] = Field(None, max_length=100)
    facebook_profile: Optional[str] = Field(None, max_length=255)

    @field_validator("phone", "alternative_phone", "emergency_contact_phone")
    @classmethod
    def validate_phone(cls, v):
        if (
            v
            and not v.replace("+", "")
            .replace("-", "")
            .replace(" ", "")
            .replace("(", "")
            .replace(")", "")
            .isdigit()
        ):
            raise ValueError(
                "Phone number must contain only digits, spaces, dashes, plus signs, "
                "and parentheses"
            )
        return v


class CustomerResponse(CustomerBase):
    """Schema for customer responses."""

    id: int
    uuid: UUID
    business_id: int

    # Customer statistics
    first_visit_date: Optional[date]
    last_visit_date: Optional[date]
    total_visits: int
    total_spent: int
    lifetime_value: float  # Computed field

    # Behavioral flags
    is_no_show_risk: bool
    no_show_count: int
    cancelled_appointment_count: int
    is_new_customer: bool  # Computed field
    risk_level: str  # Computed field

    # Data source info
    source: str
    external_id: Optional[str]

    # Relationships
    referred_by_customer_id: Optional[int]

    # Audit timestamps
    created_at: datetime
    updated_at: datetime
    last_contacted_at: Optional[datetime]

    model_config = {"from_attributes": True}


class CustomerListResponse(BaseModel):
    """Schema for paginated customer list responses."""

    customers: list[CustomerResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class CustomerSearch(BaseModel):
    """Schema for customer search parameters."""

    query: Optional[str] = Field(None, description="Search query (name, email, phone)")
    status: Optional[CustomerStatus] = Field(None, description="Filter by status")
    is_vip: Optional[bool] = Field(None, description="Filter by VIP status")
    city: Optional[str] = Field(None, description="Filter by city")
    state: Optional[str] = Field(None, description="Filter by state")
    risk_level: Optional[str] = Field(None, description="Filter by risk level")
    has_email: Optional[bool] = Field(
        None, description="Filter customers with/without email"
    )
    has_phone: Optional[bool] = Field(
        None, description="Filter customers with/without phone"
    )
    created_after: Optional[date] = Field(
        None, description="Filter customers created after date"
    )
    created_before: Optional[date] = Field(
        None, description="Filter customers created before date"
    )
    last_visit_after: Optional[date] = Field(
        None, description="Filter by last visit after date"
    )
    last_visit_before: Optional[date] = Field(
        None, description="Filter by last visit before date"
    )
    min_visits: Optional[int] = Field(
        None, ge=0, description="Minimum number of visits"
    )
    max_visits: Optional[int] = Field(
        None, ge=0, description="Maximum number of visits"
    )
    min_spent: Optional[float] = Field(None, ge=0, description="Minimum amount spent")
    max_spent: Optional[float] = Field(None, ge=0, description="Maximum amount spent")


class CustomerCSVImport(BaseModel):
    """Schema for CSV import data."""

    file_data: str = Field(..., description="Base64 encoded CSV file data")
    mapping: dict = Field(..., description="Column mapping configuration")
    skip_duplicates: bool = Field(default=True, description="Skip duplicate records")
    update_existing: bool = Field(default=False, description="Update existing records")


class CustomerCSVImportResponse(BaseModel):
    """Schema for CSV import results."""

    import_id: str = Field(..., description="Import operation ID")
    total_records: int = Field(..., description="Total records in CSV")
    imported_records: int = Field(..., description="Successfully imported records")
    updated_records: int = Field(..., description="Updated existing records")
    failed_records: int = Field(..., description="Failed import records")
    errors: list[dict] = Field(..., description="Import error details")
    warnings: list[dict] = Field(..., description="Import warnings")


class CustomerStats(BaseModel):
    """Schema for customer statistics."""

    total_customers: int
    active_customers: int
    inactive_customers: int
    blocked_customers: int
    vip_customers: int
    new_customers_this_month: int
    customers_with_appointments: int
    high_risk_customers: int
    average_lifetime_value: float
    total_customer_value: float
