from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field, model_validator
from enum import Enum

# Import enums from the model to avoid duplication
from app.models.appointment import AppointmentStatus, CancellationReason


class BookingSourceSchema(str, Enum):
    ADMIN = "admin"
    ONLINE = "online"
    PHONE = "phone"
    WALK_IN = "walk_in"


# Base appointment schemas
class AppointmentBase(BaseModel):
    customer_id: int
    staff_id: int
    service_id: int
    scheduled_datetime: datetime
    duration_minutes: int = Field(..., gt=0)
    total_price: Decimal = Field(..., ge=0)
    customer_notes: Optional[str] = None
    internal_notes: Optional[str] = None


class AppointmentCreate(AppointmentBase):
    business_id: Optional[int] = None
    booking_source: BookingSourceSchema = BookingSourceSchema.ADMIN
    booked_by_staff_id: Optional[int] = None
    addon_ids: List[int] = Field(default_factory=list)
    deposit_required: bool = False
    deposit_amount: Optional[Decimal] = Field(None, ge=0)

    @model_validator(mode="after")
    def validate_deposit_amount(self):
        if self.deposit_required and self.deposit_amount is None:
            raise ValueError("Deposit amount is required when deposit_required is True")
        if self.deposit_amount is not None and self.deposit_amount > self.total_price:
            raise ValueError("Deposit amount cannot exceed total price")
        return self


class AppointmentUpdate(BaseModel):
    scheduled_datetime: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, gt=0)
    total_price: Optional[Decimal] = Field(None, ge=0)
    customer_notes: Optional[str] = None
    internal_notes: Optional[str] = None
    deposit_required: Optional[bool] = None
    deposit_amount: Optional[Decimal] = Field(None, ge=0)
    deposit_paid: Optional[bool] = None


class AppointmentStatusTransition(BaseModel):
    new_status: AppointmentStatus
    notes: Optional[str] = None
    cancellation_reason: Optional[CancellationReason] = None
    cancellation_fee: Optional[Decimal] = Field(None, ge=0)
    no_show_fee: Optional[Decimal] = Field(None, ge=0)


class AppointmentReschedule(BaseModel):
    new_scheduled_datetime: datetime
    reason: Optional[str] = None
    notify_customer: bool = True


class AppointmentSlotLock(BaseModel):
    session_id: str
    lock_duration_minutes: int = Field(15, gt=0, le=60)


# Response schemas
class Appointment(AppointmentBase):
    id: int
    uuid: UUID
    business_id: int
    status: AppointmentStatus
    previous_status: Optional[AppointmentStatus] = None
    status_changed_at: datetime
    estimated_end_datetime: datetime
    actual_start_datetime: Optional[datetime] = None
    actual_end_datetime: Optional[datetime] = None

    # Booking details
    booked_by_staff_id: Optional[int] = None
    booking_source: BookingSourceSchema

    # Pricing and payment
    deposit_required: bool
    deposit_amount: Optional[Decimal] = None
    deposit_paid: bool
    deposit_paid_at: Optional[datetime] = None

    # Cancellation details
    is_cancelled: bool
    cancelled_at: Optional[datetime] = None
    cancelled_by_staff_id: Optional[int] = None
    cancellation_reason: Optional[CancellationReason] = None
    cancellation_notes: Optional[str] = None
    cancellation_fee: Optional[Decimal] = None

    # Rescheduling details
    original_appointment_id: Optional[int] = None
    rescheduled_from_datetime: Optional[datetime] = None
    reschedule_count: int

    # No-show details
    is_no_show: bool
    no_show_fee: Optional[Decimal] = None

    # Communication
    reminder_sent_at: Optional[datetime] = None
    confirmation_sent_at: Optional[datetime] = None

    # Slot locking
    slot_locked: bool
    slot_locked_at: Optional[datetime] = None
    slot_lock_expires_at: Optional[datetime] = None
    locked_by_session_id: Optional[str] = None

    # Timestamps
    created_at: datetime
    updated_at: datetime

    # Computed properties
    is_active: bool
    time_until_appointment: Optional[timedelta] = None
    is_past_due: bool

    class Config:
        from_attributes = True


class AppointmentWithRelations(Appointment):
    business: Optional["BusinessSummary"] = None
    customer: Optional["CustomerSummary"] = None
    staff: Optional["StaffSummary"] = None
    service: Optional["ServiceSummary"] = None
    booked_by_staff: Optional["StaffSummary"] = None
    cancelled_by_staff: Optional["StaffSummary"] = None
    original_appointment: Optional["AppointmentSummary"] = None

    class Config:
        from_attributes = True


class AppointmentSummary(BaseModel):
    id: int
    uuid: UUID
    status: AppointmentStatus
    scheduled_datetime: datetime
    duration_minutes: int
    customer_name: str
    staff_name: str
    service_name: str
    total_price: Decimal

    class Config:
        from_attributes = True


class AppointmentList(BaseModel):
    appointments: List[Appointment]
    total_count: int
    page: int
    page_size: int
    total_pages: int


# Filter and search schemas
class AppointmentFilters(BaseModel):
    business_id: Optional[int] = None
    customer_id: Optional[int] = None
    staff_id: Optional[int] = None
    service_id: Optional[int] = None
    status: Optional[AppointmentStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    booking_source: Optional[BookingSourceSchema] = None
    is_cancelled: Optional[bool] = None
    is_no_show: Optional[bool] = None
    has_deposit: Optional[bool] = None
    deposit_paid: Optional[bool] = None


class AppointmentSearch(BaseModel):
    query: Optional[str] = None  # Search customer name, phone, service name
    filters: AppointmentFilters = Field(default_factory=AppointmentFilters)
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort_by: str = Field(
        "scheduled_datetime",
        pattern=r"^(scheduled_datetime|created_at|status|customer_name|staff_name|total_price)$",
    )
    sort_order: str = Field("asc", pattern=r"^(asc|desc)$")


# Policy validation schemas
class CancellationPolicyCheck(BaseModel):
    appointment_uuid: UUID
    current_time: Optional[datetime] = None


class CancellationPolicyResponse(BaseModel):
    can_cancel: bool
    reason: str
    cancellation_fee: Optional[Decimal] = None
    cancellation_window_ends_at: Optional[datetime] = None


class ConflictCheckRequest(BaseModel):
    staff_id: int
    scheduled_datetime: datetime
    duration_minutes: int
    exclude_appointment_id: Optional[int] = None


class ConflictCheckResponse(BaseModel):
    has_conflict: bool
    conflicts: List[str] = Field(default_factory=list)
    alternative_slots: List[datetime] = Field(default_factory=list)


# Bulk operations
class BulkAppointmentStatusUpdate(BaseModel):
    appointment_uuids: List[UUID] = Field(..., min_length=1, max_length=50)
    new_status: AppointmentStatus
    notes: Optional[str] = None
    notify_customers: bool = True


class BulkAppointmentResponse(BaseModel):
    successful_updates: List[UUID]
    failed_updates: List[dict]  # [{"uuid": UUID, "error": str}, ...]
    total_processed: int


# Summary and analytics schemas
class AppointmentStats(BaseModel):
    total_appointments: int
    confirmed_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    no_show_appointments: int
    total_revenue: Decimal
    cancellation_rate: float
    no_show_rate: float
    average_appointment_value: Decimal


class DailyAppointmentSummary(BaseModel):
    date: datetime
    total_appointments: int
    confirmed_count: int
    completed_count: int
    cancelled_count: int
    no_show_count: int
    total_revenue: Decimal
    slots_available: int
    booking_rate: float


# Related model summaries (to avoid circular imports)
class BusinessSummary(BaseModel):
    id: int
    uuid: UUID
    name: str

    class Config:
        from_attributes = True


class CustomerSummary(BaseModel):
    id: int
    uuid: UUID
    first_name: str
    last_name: str

    class Config:
        from_attributes = True


class StaffSummary(BaseModel):
    id: int
    uuid: UUID
    name: str

    class Config:
        from_attributes = True


class ServiceSummary(BaseModel):
    id: int
    uuid: UUID
    name: str
    duration_minutes: int
    price: Decimal

    class Config:
        from_attributes = True


# Rebuild models to resolve forward references
AppointmentWithRelations.model_rebuild()
AppointmentSummary.model_rebuild()
