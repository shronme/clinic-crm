from datetime import datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, validator

from app.models.availability_override import OverrideType
from app.models.staff import StaffRole
from app.models.time_off import TimeOffStatus, TimeOffType
from app.models.working_hours import WeekDay


class StaffBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    role: StaffRole = StaffRole.STAFF
    is_bookable: bool = True
    is_active: bool = True
    display_order: int = 0


class StaffCreate(StaffBase):
    business_id: int


class StaffUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, max_length=20)
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    role: Optional[StaffRole] = None
    is_bookable: Optional[bool] = None
    is_active: Optional[bool] = None
    display_order: Optional[int] = None


class Staff(StaffBase):
    id: int
    uuid: UUID
    business_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StaffSummary(BaseModel):
    id: int
    uuid: UUID
    name: str
    email: Optional[str] = None
    role: StaffRole
    is_bookable: bool
    is_active: bool
    display_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class StaffWithServices(Staff):
    staff_services: list[dict]

    class Config:
        from_attributes = True


class WorkingHoursBase(BaseModel):
    weekday: WeekDay
    start_time: time
    end_time: time
    break_start_time: Optional[time] = None
    break_end_time: Optional[time] = None
    is_active: bool = True
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None

    @validator("end_time")
    def end_time_after_start_time(cls, v, values):
        if "start_time" in values and v <= values["start_time"]:
            raise ValueError("End time must be after start time")
        return v

    @validator("break_end_time")
    def break_times_valid(cls, v, values):
        if v and "break_start_time" not in values:
            raise ValueError("Break start time required when break end time is set")
        if v and "break_start_time" in values and v <= values["break_start_time"]:
            raise ValueError("Break end time must be after break start time")
        return v


class WorkingHoursCreate(WorkingHoursBase):
    pass


class WorkingHoursUpdate(BaseModel):
    weekday: Optional[WeekDay] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    break_start_time: Optional[time] = None
    break_end_time: Optional[time] = None
    is_active: Optional[bool] = None
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None


class WorkingHours(WorkingHoursBase):
    id: int
    uuid: UUID
    owner_type: str
    owner_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TimeOffBase(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    type: TimeOffType = TimeOffType.PERSONAL
    reason: Optional[str] = None
    notes: Optional[str] = None
    is_all_day: bool = False
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None

    @validator("end_datetime")
    def end_after_start(cls, v, values):
        if "start_datetime" in values and v <= values["start_datetime"]:
            raise ValueError("End datetime must be after start datetime")
        return v


class TimeOffCreate(TimeOffBase):
    pass


class TimeOffUpdate(BaseModel):
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    type: Optional[TimeOffType] = None
    reason: Optional[str] = None
    notes: Optional[str] = None
    is_all_day: Optional[bool] = None
    status: Optional[TimeOffStatus] = None
    approval_notes: Optional[str] = None


class TimeOff(TimeOffBase):
    id: int
    uuid: UUID
    owner_type: str
    owner_id: int
    status: TimeOffStatus
    approved_by_staff_id: Optional[int] = None
    approved_at: Optional[datetime] = None
    approval_notes: Optional[str] = None
    parent_timeoff_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AvailabilityOverrideBase(BaseModel):
    override_type: OverrideType
    start_datetime: datetime
    end_datetime: datetime
    title: Optional[str] = None
    reason: Optional[str] = None
    is_active: bool = True
    allow_new_bookings: bool = True
    max_concurrent_appointments: Optional[int] = None

    @validator("end_datetime")
    def end_after_start(cls, v, values):
        if "start_datetime" in values and v <= values["start_datetime"]:
            raise ValueError("End datetime must be after start datetime")
        return v

    @validator("max_concurrent_appointments")
    def max_appointments_positive(cls, v):
        if v is not None and v < 1:
            raise ValueError("Max concurrent appointments must be positive")
        return v


class AvailabilityOverrideCreate(AvailabilityOverrideBase):
    staff_id: int


class AvailabilityOverrideUpdate(BaseModel):
    override_type: Optional[OverrideType] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    title: Optional[str] = None
    reason: Optional[str] = None
    is_active: Optional[bool] = None
    allow_new_bookings: Optional[bool] = None
    max_concurrent_appointments: Optional[int] = None


class AvailabilityOverride(AvailabilityOverrideBase):
    id: int
    uuid: UUID
    staff_id: int
    created_by_staff_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StaffServiceOverride(BaseModel):
    service_id: UUID
    override_duration_minutes: Optional[int] = None
    override_price: Optional[float] = None
    override_buffer_before_minutes: Optional[int] = None
    override_buffer_after_minutes: Optional[int] = None
    is_available: bool = True
    expertise_level: Optional[str] = None
    notes: Optional[str] = None
    requires_approval: bool = False

    @validator(
        "override_duration_minutes",
        "override_buffer_before_minutes",
        "override_buffer_after_minutes",
    )
    def positive_minutes(cls, v):
        if v is not None and v < 0:
            raise ValueError("Minutes must be non-negative")
        return v

    @validator("override_price")
    def positive_price(cls, v):
        if v is not None and v < 0:
            raise ValueError("Price must be non-negative")
        return v


class StaffAvailabilityQuery(BaseModel):
    """Query parameters for staff availability checks"""

    start_datetime: datetime
    end_datetime: datetime
    service_ids: Optional[list[int]] = None
    include_overrides: bool = True
    include_time_offs: bool = True


class StaffAvailabilitySlot(BaseModel):
    """Available time slot for staff"""

    start_datetime: datetime
    end_datetime: datetime
    is_available: bool
    availability_type: str  # 'normal', 'override', 'limited'
    restrictions: Optional[dict] = None


class StaffAvailabilityResponse(BaseModel):
    """Staff availability response"""

    staff_id: int
    query_period: StaffAvailabilityQuery
    available_slots: list[StaffAvailabilitySlot]
    unavailable_periods: list[dict]  # Time-off periods, overrides, etc.
    working_hours_summary: list[dict]  # Weekly schedule summary
