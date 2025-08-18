from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

def validate_timezone(timezone: str) -> str:
    """Validate timezone string."""
    import pytz
    try:
        pytz.timezone(timezone)
    except pytz.UnknownTimeZoneError:
        raise ValueError(f"Invalid timezone: {timezone}")
    return timezone

def validate_currency(currency: str) -> str:
    """Validate currency code."""
    valid_currencies = ["USD", "EUR", "GBP", "CAD", "AUD", "JPY", "CHF", "CNY", "INR"]
    if currency not in valid_currencies:
        raise ValueError(f"Unsupported currency: {currency}. Supported: {', '.join(valid_currencies)}")
    return currency

class BusinessBranding(BaseModel):
    """Business branding configuration."""
    primary_color: Optional[str] = Field(None, description="Primary brand color (hex)")
    secondary_color: Optional[str] = Field(None, description="Secondary brand color (hex)")
    logo_position: Optional[str] = Field("center", description="Logo position on booking portal")
    custom_css: Optional[str] = Field(None, description="Custom CSS for booking portal")

class BusinessPolicy(BaseModel):
    """Business booking policies."""
    min_lead_time_hours: int = Field(1, ge=0, description="Minimum hours before appointment can be booked")
    max_lead_time_days: int = Field(90, ge=1, description="Maximum days in advance appointments can be booked")
    cancellation_window_hours: int = Field(6, ge=0, description="Hours before appointment when free cancellation ends")
    deposit_required: bool = Field(False, description="Whether deposits are required")
    no_show_fee: Optional[float] = Field(None, ge=0, description="Fee charged for no-shows")
    late_arrival_grace_minutes: int = Field(15, ge=0, description="Grace period for late arrivals")

class BusinessBase(BaseModel):
    """Base business schema with common fields."""
    name: str = Field(..., min_length=1, max_length=255, description="Business name")
    logo_url: Optional[str] = Field(None, max_length=500, description="URL to business logo")
    description: Optional[str] = Field(None, description="Business description")
    phone: Optional[str] = Field(None, max_length=50, description="Business phone number")
    email: Optional[str] = Field(None, max_length=255, description="Business email address")
    website: Optional[str] = Field(None, max_length=500, description="Business website URL")
    address: Optional[str] = Field(None, description="Business address")
    timezone: str = Field("UTC", max_length=50, description="Business timezone")
    currency: str = Field("USD", max_length=10, description="Business currency code")
    branding: Optional[BusinessBranding] = Field(None, description="Branding configuration")
    policy: Optional[BusinessPolicy] = Field(None, description="Booking policies")

    @field_validator('timezone')
    @classmethod
    def validate_timezone_field(cls, v):
        return validate_timezone(v)

    @field_validator('currency')
    @classmethod
    def validate_currency_field(cls, v):
        return validate_currency(v)

class BusinessCreate(BusinessBase):
    """Schema for creating a new business."""
    pass

class BusinessUpdate(BaseModel):
    """Schema for updating business information."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    logo_url: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    website: Optional[str] = Field(None, max_length=500)
    address: Optional[str] = None
    timezone: Optional[str] = Field(None, max_length=50)
    currency: Optional[str] = Field(None, max_length=10)
    branding: Optional[BusinessBranding] = None
    policy: Optional[BusinessPolicy] = None
    is_active: Optional[bool] = None

    @field_validator('timezone')
    @classmethod
    def validate_timezone_field(cls, v):
        if v is not None:
            return validate_timezone(v)
        return v

    @field_validator('currency')
    @classmethod
    def validate_currency_field(cls, v):
        if v is not None:
            return validate_currency(v)
        return v

class BusinessResponse(BusinessBase):
    """Schema for business responses."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}