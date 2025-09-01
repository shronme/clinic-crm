import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class OwnerType(enum.Enum):
    BUSINESS = "BUSINESS"
    STAFF = "STAFF"


class TimeOffType(enum.Enum):
    VACATION = "VACATION"
    SICK_LEAVE = "SICK_LEAVE"
    PERSONAL = "PERSONAL"
    TRAINING = "TRAINING"
    HOLIDAY = "HOLIDAY"
    MAINTENANCE = "MAINTENANCE"
    OTHER = "OTHER"


class TimeOffStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    CANCELLED = "CANCELLED"


class TimeOff(Base):
    """Time-off model for businesses and staff with approval workflow."""

    __tablename__ = "time_off"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    owner_type = Column(String(20), nullable=False)
    owner_id = Column(Integer, nullable=False)

    # Time-off period
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=False)

    # Type and details
    type = Column(String(20), nullable=False, default="PERSONAL")
    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Approval workflow
    status = Column(String(20), nullable=False, default="PENDING")
    approved_by_staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approval_notes = Column(Text, nullable=True)

    # Recurring time-off support
    is_recurring = Column(Boolean, default=False, nullable=False)
    recurrence_pattern = Column(String, nullable=True)  # RRULE format
    parent_timeoff_id = Column(Integer, ForeignKey("time_off.id"), nullable=True)

    # All-day flag
    is_all_day = Column(Boolean, default=False, nullable=False)

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Note: Polymorphic relationships with Business and Staff
    # These are managed through the owner_type and owner_id fields
    # Direct relationships are handled in the respective models

    # Self-referential relationship for recurring time-off
    children = relationship(
        "TimeOff", back_populates="parent", cascade="all, delete-orphan"
    )
    parent = relationship("TimeOff", back_populates="children", remote_side=[id])

    # Approval relationship
    approved_by = relationship("Staff", foreign_keys=[approved_by_staff_id])

    # Database constraints
    __table_args__ = (
        Index("ix_time_off_owner", "owner_type", "owner_id"),
        Index("ix_time_off_dates", "start_datetime", "end_datetime"),
        Index("ix_time_off_status", "status"),
    )

    @property
    def duration_hours(self):
        """Calculate duration in hours."""
        return (self.end_datetime - self.start_datetime).total_seconds() / 3600

    @property
    def duration_days(self):
        """Calculate duration in days."""
        return (self.end_datetime.date() - self.start_datetime.date()).days + 1

    def overlaps_with(self, start_dt, end_dt):
        """Check if this time-off overlaps with a given time period."""
        if self.status != TimeOffStatus.APPROVED.value:
            return False

        return not (end_dt <= self.start_datetime or start_dt >= self.end_datetime)

    def is_active_at(self, check_datetime):
        """Check if time-off is active at a specific datetime."""
        if self.status != TimeOffStatus.APPROVED.value:
            return False

        return self.start_datetime <= check_datetime <= self.end_datetime

    def can_be_modified_by(self, staff_id, staff_role):
        """Check if a staff member can modify this time-off."""
        from app.models.staff import StaffRole

        # Owner can always modify (if pending)
        if self.owner_type == OwnerType.STAFF.value and self.owner_id == staff_id:
            return self.status == TimeOffStatus.PENDING.value

        # Admin/Owner can modify any - handle both enum and string values
        admin_roles = [StaffRole.OWNER_ADMIN.value, "owner_admin"]
        if staff_role in admin_roles:
            return True

        return False

    def __repr__(self):
        owner_type_str = (
            self.owner_type.value
            if hasattr(self.owner_type, "value")
            else str(self.owner_type)
        )
        type_str = self.type.value if hasattr(self.type, "value") else str(self.type)
        status_str = (
            self.status.value if hasattr(self.status, "value") else str(self.status)
        )
        return (
            f"<TimeOff(id={self.id}, {owner_type_str}_id={self.owner_id}, "
            f"type={type_str}, status={status_str}, "
            f"{self.start_datetime.date()} - {self.end_datetime.date()})>"
        )
