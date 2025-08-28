from datetime import datetime, time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class AvailabilityStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    BUSY = "busy"
    BLOCKED = "blocked"


class ConflictType(str, Enum):
    EXISTING_APPOINTMENT = "existing_appointment"
    TIME_OFF = "time_off"
    OUTSIDE_WORKING_HOURS = "outside_working_hours"
    INSUFFICIENT_BUFFER = "insufficient_buffer"
    LEAD_TIME_VIOLATION = "lead_time_violation"
    ADVANCE_BOOKING_VIOLATION = "advance_booking_violation"
    AVAILABILITY_OVERRIDE = "availability_override"
    STAFF_UNAVAILABLE = "staff_unavailable"


class AvailabilitySlot(BaseModel):
    start_datetime: datetime
    end_datetime: datetime
    status: AvailabilityStatus
    staff_uuid: str
    service_uuid: Optional[str] = None
    conflicts: List[ConflictType] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StaffAvailabilityQuery(BaseModel):
    staff_uuid: str
    start_datetime: datetime
    end_datetime: datetime
    service_uuid: Optional[str] = None
    include_busy_slots: bool = False
    slot_duration_minutes: int = 15


class SchedulingConflict(BaseModel):
    conflict_type: ConflictType
    message: str
    start_datetime: datetime
    end_datetime: datetime
    conflicting_entity_uuid: Optional[str] = None
    severity: str = "error"  # error, warning, info


class AppointmentValidationRequest(BaseModel):
    staff_uuid: str
    service_uuid: str
    requested_datetime: datetime
    customer_uuid: Optional[str] = None
    addon_uuids: List[str] = Field(default_factory=list)


class AppointmentValidationResponse(BaseModel):
    is_valid: bool
    conflicts: List[SchedulingConflict] = Field(default_factory=list)
    alternative_slots: List[AvailabilitySlot] = Field(default_factory=list)
    total_duration_minutes: int
    estimated_end_time: datetime


class BusinessHoursQuery(BaseModel):
    business_uuid: str
    date: datetime
    include_breaks: bool = True


class StaffScheduleQuery(BaseModel):
    staff_uuid: str
    start_date: datetime
    end_date: datetime
    include_appointments: bool = True
    include_time_off: bool = True
    include_availability_overrides: bool = True