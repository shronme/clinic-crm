from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# Service Category Schemas
class ServiceCategoryBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: int = 0
    is_active: bool = True
    icon: Optional[str] = Field(None, max_length=100)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class ServiceCategoryCreate(ServiceCategoryBase):
    business_id: Optional[int] = Field(
        None, description="Business ID (set by dependency injection)"
    )


class ServiceCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None
    icon: Optional[str] = Field(None, max_length=100)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class ServiceCategory(ServiceCategoryBase):
    id: int
    uuid: UUID
    business_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Service Schemas
class ServiceBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    category_id: Optional[int] = None
    duration_minutes: int = Field(..., gt=0)
    price: Decimal = Field(..., ge=0)
    buffer_before_minutes: int = Field(0, ge=0)
    buffer_after_minutes: int = Field(0, ge=0)
    is_active: bool = True
    requires_deposit: bool = False
    deposit_amount: Optional[Decimal] = Field(None, ge=0)
    max_advance_booking_days: Optional[int] = Field(None, gt=0)
    min_lead_time_hours: Optional[int] = Field(None, ge=0)
    sort_order: int = 0
    image_url: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")

    @model_validator(mode="after")
    def validate_deposit_amount(self):
        if self.requires_deposit and self.deposit_amount is None:
            raise ValueError("Deposit amount is required when requires_deposit is True")
        return self


class ServiceCreate(ServiceBase):
    business_id: Optional[int] = Field(
        None, description="Business ID (set by dependency injection)"
    )


class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    category_id: Optional[int] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    price: Optional[Decimal] = Field(None, ge=0)
    buffer_before_minutes: Optional[int] = Field(None, ge=0)
    buffer_after_minutes: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None
    requires_deposit: Optional[bool] = None
    deposit_amount: Optional[Decimal] = Field(None, ge=0)
    max_advance_booking_days: Optional[int] = Field(None, gt=0)
    min_lead_time_hours: Optional[int] = Field(None, ge=0)
    sort_order: Optional[int] = None
    image_url: Optional[str] = Field(None, max_length=500)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")


class Service(ServiceBase):
    id: int
    uuid: UUID
    business_id: int
    total_duration_minutes: int
    created_at: datetime
    updated_at: datetime
    category: Optional[ServiceCategory] = None

    class Config:
        from_attributes = True


# Service Add-on Schemas
class ServiceAddonBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    extra_duration_minutes: int = Field(0, ge=0)
    price: Decimal = Field(..., ge=0)
    is_active: bool = True
    is_required: bool = False
    max_quantity: int = Field(1, gt=0)
    sort_order: int = 0


class ServiceAddonCreate(ServiceAddonBase):
    business_id: Optional[int] = Field(
        None, description="Business ID (set by dependency injection)"
    )
    service_id: int


class ServiceAddonUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    extra_duration_minutes: Optional[int] = Field(None, ge=0)
    price: Optional[Decimal] = Field(None, ge=0)
    is_active: Optional[bool] = None
    is_required: Optional[bool] = None
    max_quantity: Optional[int] = Field(None, gt=0)
    sort_order: Optional[int] = None


class ServiceAddon(ServiceAddonBase):
    id: int
    business_id: int
    service_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Staff Service Mapping Schemas
class StaffServiceBase(BaseModel):
    override_duration_minutes: Optional[int] = Field(None, gt=0)
    override_price: Optional[Decimal] = Field(None, ge=0)
    override_buffer_before_minutes: Optional[int] = Field(None, ge=0)
    override_buffer_after_minutes: Optional[int] = Field(None, ge=0)
    is_available: bool = True
    expertise_level: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    requires_approval: bool = False


class StaffServiceCreate(StaffServiceBase):
    staff_id: int
    service_id: int


class StaffServiceUpdate(StaffServiceBase):
    is_available: Optional[bool] = None


class StaffService(StaffServiceBase):
    id: int
    staff_id: int
    service_id: int
    effective_duration_minutes: int
    effective_price: Decimal
    effective_buffer_before_minutes: int
    effective_buffer_after_minutes: int
    effective_total_duration_minutes: int
    created_at: datetime
    updated_at: datetime
    service: Service

    class Config:
        from_attributes = True
