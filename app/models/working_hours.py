import enum
import uuid

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class OwnerType(enum.Enum):
    BUSINESS = "BUSINESS"
    STAFF = "STAFF"


class WeekDay(enum.Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class WorkingHours(Base):
    """Working hours model for businesses and staff with break support."""

    __tablename__ = "working_hours"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    owner_type = Column(String(20), nullable=False)
    owner_id = Column(Integer, nullable=False)

    # Schedule details
    weekday = Column(String(20), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)

    # Break configuration (optional)
    break_start_time = Column(Time, nullable=True)
    break_end_time = Column(Time, nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Effective date range (for temporary overrides)
    effective_from = Column(DateTime(timezone=True), nullable=True)
    effective_until = Column(DateTime(timezone=True), nullable=True)

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Note: Polymorphic relationships with Business and Staff
    # These are managed through the owner_type and owner_id fields
    # Direct relationships are handled in the respective models

    # Database constraints
    __table_args__ = (
        Index("ix_working_hours_owner", "owner_type", "owner_id"),
        Index("ix_working_hours_weekday", "weekday"),
    )

    def duration_minutes(self):
        """Calculate working duration in minutes, accounting for breaks."""
        from datetime import datetime

        # Convert times to datetime for calculation
        start_dt = datetime.combine(datetime.today(), self.start_time)
        end_dt = datetime.combine(datetime.today(), self.end_time)

        total_minutes = int((end_dt - start_dt).total_seconds() / 60)
        print(f"Total minutes: {total_minutes}")
        # Subtract break time if configured
        if self.break_start_time and self.break_end_time:
            break_start_dt = datetime.combine(datetime.today(), self.break_start_time)
            break_end_dt = datetime.combine(datetime.today(), self.break_end_time)
            break_minutes = int((break_end_dt - break_start_dt).total_seconds() / 60)
            print(f"Break minutes: {break_minutes}")
            total_minutes -= break_minutes
        print(f"Total minutes after break: {total_minutes}")
        return max(0, total_minutes)

    def is_time_available(self, check_time):
        """Check if a given time falls within working hours but outside break times."""
        if not self.is_active:
            return False

        # Check if time is within working hours
        if not (self.start_time <= check_time.time() <= self.end_time):
            return False

        # Check if time falls during break
        if (
            self.break_start_time
            and self.break_end_time
            and self.break_start_time < check_time.time() < self.break_end_time
        ):
            return False

        return True

    def __repr__(self):
        break_info = ""
        if self.break_start_time and self.break_end_time:
            break_info = f", break={self.break_start_time}-{self.break_end_time}"

        # Handle both enum and string values for owner_type and weekday
        owner_type_str = (
            self.owner_type.value
            if hasattr(self.owner_type, "value")
            else str(self.owner_type)
        )
        weekday_str = (
            self.weekday.name if hasattr(self.weekday, "name") else str(self.weekday)
        )

        return (
            f"<WorkingHours(id={self.id}, "
            f"{owner_type_str}_id={self.owner_id}, "
            f"{weekday_str}: {self.start_time}-{self.end_time}"
            f"{break_info})>"
        )
