from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    Index,
    Enum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum
import uuid


class OverrideType(enum.Enum):
    AVAILABLE = "available"  # Make staff available during normally unavailable times
    UNAVAILABLE = (
        "unavailable"  # Make staff unavailable during normally available times
    )
    CUSTOM_HOURS = "custom_hours"  # Custom working hours for specific date/time


class AvailabilityOverride(Base):
    """Availability override model for temporary staff availability changes."""

    __tablename__ = "availability_overrides"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)

    # Override details
    override_type = Column(Enum(OverrideType), nullable=False)
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=False)

    # Override description and reason
    title = Column(String, nullable=True)
    reason = Column(Text, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Booking restrictions during override
    allow_new_bookings = Column(Boolean, default=True, nullable=False)
    max_concurrent_appointments = Column(Integer, nullable=True)

    # Creator tracking
    created_by_staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    staff = relationship(
        "Staff", foreign_keys=[staff_id], back_populates="availability_overrides"
    )
    created_by = relationship("Staff", foreign_keys=[created_by_staff_id])

    # Database constraints
    __table_args__ = (
        Index("ix_availability_override_staff", "staff_id"),
        Index("ix_availability_override_dates", "start_datetime", "end_datetime"),
        Index("ix_availability_override_type", "override_type"),
    )

    @property
    def duration_hours(self):
        """Calculate override duration in hours."""
        return (self.end_datetime - self.start_datetime).total_seconds() / 3600

    @property
    def duration_days(self):
        """Calculate override duration in days."""
        return (self.end_datetime.date() - self.start_datetime.date()).days + 1

    def is_active_at(self, check_datetime):
        """Check if override is active at a specific datetime."""
        if not self.is_active:
            return False

        return self.start_datetime <= check_datetime <= self.end_datetime

    def overlaps_with(self, start_dt, end_dt):
        """Check if this override overlaps with a given time period."""
        if not self.is_active:
            return False

        return not (end_dt <= self.start_datetime or start_dt >= self.end_datetime)

    def affects_availability_at(self, check_datetime):
        """
        Determine how this override affects availability at a specific time.
        Returns: 'available', 'unavailable', or None if override doesn't apply
        """
        if not self.is_active_at(check_datetime):
            return None

        if self.override_type == OverrideType.AVAILABLE:
            return "available"
        elif self.override_type == OverrideType.UNAVAILABLE:
            return "unavailable"
        elif self.override_type == OverrideType.CUSTOM_HOURS:
            return "available"

        return None

    def can_accept_new_bookings_at(self, check_datetime):
        """Check if new bookings can be accepted during this override."""
        if not self.is_active_at(check_datetime):
            return True  # Override doesn't apply

        return self.allow_new_bookings

    def __repr__(self):
        return (
            f"<AvailabilityOverride(id={self.id}, staff_id={self.staff_id}, "
            f"type={self.override_type.value}, "
            f"{self.start_datetime.date()} - {self.end_datetime.date()}, "
            f"active={self.is_active})>"
        )
